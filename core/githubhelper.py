import base64
import re
from collections import defaultdict
from datetime import datetime
from socket import gaierror
import time
from urllib.error import URLError
from io import BytesIO
from zipfile import ZipFile

import requests
import structlog
from dateutil.parser import parse
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from fastcore.net import (
    HTTP401UnauthorizedError,
    HTTP404NotFoundError,
    HTTP422UnprocessableEntityError,
)
from fastcore.xtras import obj2dict
from ghapi.all import GhApi, paged

logger = structlog.get_logger()


class GithubAPIClient:
    """A class to interact with the GitHub API."""

    def __init__(
        self,
        owner: str = "boostorg",
        ref: str = "heads/master",
        repo_slug: str = "boost",
        token: str = None,
    ) -> None:
        """
        Initialize the GitHubAPIClient.

        :param owner: str, the repository owner
        :param ref: str, the Git reference
        :param repo_slug: str, the repository slug
        """
        self.token = token or settings.GITHUB_TOKEN
        self.api = self.initialize_api()
        self.owner = owner
        self.ref = ref
        self.repo_slug = repo_slug
        self.logger = structlog.get_logger()

        # Modules we need to skip as they are not really Boost Libraries
        self.skip_modules = [
            "inspect",
            "boostbook",
            "bcp",
            "build",
            "quickbook",
            "litre",
            "auto_index",
            "boostdep",
            "check_build",
            "headers",
            "boost_install",
            "docca",
            "cmake",
            "more",
        ]
        if not self.token:
            raise ValueError("No GitHub token provided or set in environment.")

    def initialize_api(self) -> GhApi:
        """
        Initialize the GitHub API with the token from the environment variable.

        :return: GhApi, the GitHub API
        """
        return GhApi(token=self.token)

    def is_authenticated(self) -> bool:
        if not self.api:
            return False
        try:
            user = self.api.users.get_authenticated()
            return bool(user)
        except HTTP401UnauthorizedError:
            return False

    def with_retry(self, fn, retry_count=5):
        count = 0
        while count < 5:
            count += 1
            try:
                output = fn()
            except URLError as e:
                if getattr(e, "args", None) and isinstance(
                    e.args[0], gaierror
                ):  # connection error
                    if count == retry_count:
                        raise e
                    self.logger.warning(f"URLError: {e}")
                    self.logger.info(f"Retry backoff {2**count} seconds.")
                    time.sleep(2**count)
                else:
                    raise e
            else:
                return output

    def get_blob(self, repo_slug: str = None, file_sha: str = None) -> dict:
        """
        Get the blob from the GitHub API.

        :param repo_slug: str, the repository slug
        :param file_sha: str, the file sha
        :return: dict, the blob
        """
        if not repo_slug:
            repo_slug = self.repo_slug
        return self.api.git.get_blob(
            owner=self.owner, repo=repo_slug, file_sha=file_sha
        )

    def get_commit_by_sha(self, repo_slug: str = None, commit_sha: str = None) -> dict:
        """Get a commit by its SHA."""
        if not repo_slug:
            repo_slug = self.repo_slug
        return self.api.git.get_commit(
            owner=self.owner, repo=repo_slug, commit_sha=commit_sha
        )

    def get_repo_ref(self, repo_slug: str = None, ref: str = None) -> dict:
        """Get a repo commit by ref."""
        if not repo_slug:
            repo_slug = self.repo_slug
        return self.with_retry(
            lambda: self.api.repos.get_commit(owner=self.owner, repo=repo_slug, ref=ref)
        )

    def get_commits(
        self,
        repo_slug: str = None,
        branch: str = "master",
        since: datetime = None,
        until: datetime = None,
    ) -> list:
        """Get all commits to the specified branch of a repo.

        :param repo_slug: str, the repository slug. If not provided, the class
            instance's repo_slug will be used.
        :param branch: str, the branch name. Defaults to 'master'.
        :param since: datetime, only return commits after this date.
        :param until: datetime, only return commits before this date.
        :return: List[Commit], list of all commits in the branch.
        """
        repo_slug = repo_slug or self.repo_slug

        # Get the commits
        try:
            pages = list(
                paged(
                    self.api.repos.list_commits,
                    owner=self.owner,
                    repo=repo_slug,
                    sha=branch,
                    since=since,
                    until=until,
                    per_page=100,
                )
            )
            all_commits = []
            for page in pages:
                all_commits.extend(page)

        except Exception as e:
            self.logger.exception(
                "get_all_commits_failed", repo=repo_slug, exc_msg=str(e)
            )
            return []

        return all_commits

    def compare(
        self,
        repo_slug: str = None,
        ref_from: str = None,
        ref_to: str = None,
    ):
        """Compare and get commits between 2 refs.

        :param repo_slug: str, the repository slug. If not provided, the class
            instance's repo_slug will be used.
        :param ref_from: str, the ref to start from.
        :param ref_to: str, the ref to end with.
        :return: List[ComparePage], list of the pages returned by compare_commits
        """
        repo_slug = repo_slug or self.repo_slug

        # Get the commits
        all_pages = []
        basehead = f"{ref_from}...{ref_to}"

        try:
            page = 1
            per_page = 100
            while True:
                output = self.with_retry(
                    lambda: self.api.repos.compare_commits(
                        owner=self.owner,
                        repo=repo_slug,
                        basehead=basehead,
                        per_page=per_page,
                        page=page,
                    )
                )
                if not output:
                    break
                all_pages.append(output)
                if len(output["commits"]) < per_page:
                    break
                page += 1

        except Exception as e:
            self.logger.exception(
                "compare refs failed",
                repo=repo_slug,
                ref_from=ref_from,
                ref_to=ref_to,
                exc_msg=str(e),
            )
            return []

        return all_pages

    def get_first_tag(self, repo_slug: str = None):
        """
        Retrieves the earliest tag in the repo.

        :param repo_slug: str, the repository slug
        :return: tuple with GitHub tag object, commit date.
        - See https://docs.github.com/en/rest/git/tags for tag object format.
        """
        if not repo_slug:
            repo_slug = self.repo_slug

        try:
            per_page = 100
            page = 1
            all_tags = []

            while True:
                tags = self.api.repos.list_tags(
                    owner=self.owner, repo=repo_slug, per_page=per_page, page=page
                )
                all_tags.extend(tags)
                if len(tags) < per_page:  # End of results
                    break

                page += 1  # Go to the next page

            # Sort the tags by the commit date. The first tag will be the earliest.
            # The Github API doesn't return the commit date with the tag, so we have to
            # retrieve each one individually. This is slow, but it's the only way to get
            # the commit date.
            def get_tag_commit_date(tag):
                """Get the commit date for a tag.

                For commit format, see
                https://docs.github.com/en/rest/commits/commits."""
                commit_sha = tag["commit"]["sha"]
                commit = self.get_commit_by_sha(repo_slug, commit_sha)
                return commit["committer"]["date"]

            annotated_tags = [(tag, get_tag_commit_date(tag)) for tag in all_tags]
            sorted_tags = sorted(annotated_tags, key=lambda x: x[1])

            # Return the first (earliest) tag
            return sorted_tags[0]

        except Exception:
            self.logger.exception("get_first_tag_and_date_failed", repo=repo_slug)
            return None

    def get_gitmodules(self, repo_slug: str = None, ref: str = None) -> str:
        """
        Get the .gitmodules file for the repo from the GitHub API.

        :param repo_slug: str, the repository slug
        :param ref: dict, the Git reference object (the commit hash).
            See https://docs.github.com/en/rest/git/refs for expected format.
        :return: str, the .gitmodules file from the repo
        """
        if not repo_slug:
            repo_slug = self.repo_slug

        if not ref:
            ref = self.get_ref()
        tree_sha = ref["object"]["sha"]

        try:
            tree = self.get_tree(tree_sha=tree_sha)
        except HTTP422UnprocessableEntityError as e:
            # Only happens for version 1.61.0; uncertain why.
            self.logger.exception(
                "get_gitmodules_failed", repo=repo_slug, exc_msg=str(e)
            )
            return None

        for item in tree["tree"]:
            if item["path"] == ".gitmodules":
                file_sha = item["sha"]
                blob = self.get_blob(repo_slug=repo_slug, file_sha=file_sha)
                return base64.b64decode(blob["content"])

    def get_libraries_json(self, repo_slug: str, tag: str = "master"):
        """
        Retrieve library metadata from 'meta/libraries.json'
        Each Boost library will have a `meta` directory with a `libraries.json` file.
        Example:
        https://github.com/boostorg/align/blob/5ad7df63cd792fbdb801d600b93cad1a432f0151/meta/libraries.json
        """
        url = f"https://raw.githubusercontent.com/{self.owner}/{repo_slug}/{tag}/meta/libraries.json"  # noqa

        try:
            response = requests.get(url)
            response.raise_for_status()
        # This usually happens because the library does not have a `meta/libraries.json`
        # in the requested tag. More likely to happen with older versions of libraries.
        except requests.exceptions.HTTPError:
            self.logger.warning(f"get_library_metadata_failed {repo_slug=}, {url=}")
            return None
        else:
            return response.json()

    def get_file_content(
        self,
        repo_slug: str = None,
        tag: str = "master",
        file_path: str = "library-detail.adoc",
    ) -> str:
        """
        Get the specified file for the repo from the GitHub API, if it exists.

        :param repo_slug: str, the repository slug
        :param tag: str, the Git tag
        :param file_name: str, the name of the file to fetch. Should be
                          "library-detail.adoc" or "README.md".
        :return: str, the specified file content from the repo
        """
        url = f"https://raw.githubusercontent.com/{self.owner}/{repo_slug}/{tag}/{file_path}"  # noqa

        response = requests.get(url)

        if not response.status_code == 200:
            logger.exception(
                "get_file_content_failed", repo=repo_slug, url=url, file=file_path
            )
            return None

        return response.content

    def get_ref(self, repo_slug: str = None, ref: str = None) -> dict:
        """
        Get the ref from the GitHub API.

        :param repo_slug: str, the repository slug
        :param ref: str, the Git reference
        :return: dict, the ref
        """
        if not repo_slug:
            repo_slug = self.repo_slug
        if not ref:
            ref = self.ref
        try:
            ref_response = self.api.git.get_ref(
                owner=self.owner, repo=repo_slug, ref=ref
            )
        except OSError as e:
            logger.warning("get_ref_failed", repo=repo_slug, ref=ref, exc_msg=str(e))
            raise ValueError(f"Could not get ref for {repo_slug} and {ref}")
        return ref_response

    def get_repo(self, repo_slug: str = None) -> dict:
        """
        Get the repository from the GitHub API.

        :param repo_slug: str, the repository slug
        :return: dict, the repository
        """
        if not repo_slug:
            repo_slug = self.repo_slug

        try:
            return self.api.repos.get(owner=self.owner, repo=repo_slug)
        except HTTP404NotFoundError as e:
            logger.info("repo_not_found", repo_slug=repo_slug, exc_msg=str(e))
            return

    def get_repo_issues(
        self, owner: str, repo_slug: str, state: str = "all", issues_only: bool = True
    ):
        """
        Get all issues for a repo.
        Note: The GitHub API considers both PRs and Issues to be "Issues" and does not
        support filtering in the request, so to exclude PRs from the list of issues, we
        do some manual filtering of the results

        Note: GhApi() returns results as AttrDict objects:
        https://fastcore.fast.ai/basics.html#attrdict
        """
        pages = list(
            self.with_retry(
                lambda: paged(
                    self.api.issues.list_for_repo,
                    owner=self.owner,
                    repo=repo_slug,
                    state=state,
                    per_page=100,
                )
            )
        )
        # Concatenate all pages into a single list
        all_results = []
        for page in pages:
            all_results.extend(page)

        # Filter results
        results = []
        if issues_only:
            results = [
                result for result in all_results if not result.get("pull_request")
            ]
        else:
            results = all_results

        return results

    def get_repo_prs(self, repo_slug, state="all"):
        """
        Get all PRs for a repo
        Note: GhApi() returns results as AttrDict objects:
        https://fastcore.fast.ai/basics.html#attrdict
        """
        pages = list(
            paged(
                self.api.pulls.list,
                owner=self.owner,
                repo=repo_slug,
                state=state,
                per_page=100,
            )
        )
        # Concatenate all pages into a single list
        results = []
        for p in pages:
            results.extend(p)

        return results

    def get_release_by_tag(self, tag_name: str, repo_slug: str = None) -> dict:
        """Get a tag by name from the GitHub API."""
        if not repo_slug:
            repo_slug = self.repo_slug
        try:
            return self.api.repos.get_release_by_tag(
                owner=self.owner, repo=repo_slug, tag=tag_name
            )
        except Exception:
            # Not necessarily an error, so log it but don't raise.
            logger.info(
                "release_by_tag_not_found", tag_name=tag_name, repo_slug=repo_slug
            )
            return

    def get_tags(self, repo_slug: str = None) -> list:
        """Get all the tags from the GitHub API."""
        if not repo_slug:
            repo_slug = self.repo_slug

        per_page = 50
        page = 1
        tags = []

        while True:
            new_tags = self.api.repos.list_tags(
                owner=self.owner, repo=repo_slug, per_page=per_page, page=page
            )
            tags.extend(new_tags)

            # Check if we reached the last page
            if len(new_tags) < per_page:
                break

            page += 1

        return tags

    def get_tree(self, repo_slug: str = None, tree_sha: str = None) -> dict:
        """
        Get the tree from the GitHub API.

        :param repo_slug: str, the repository slug
        :param tree_sha: str, the tree sha
        :return: dict, the tree
        """
        if not repo_slug:
            repo_slug = self.repo_slug
        return self.api.git.get_tree(
            owner=self.owner, repo=repo_slug, tree_sha=tree_sha
        )

    def get_user_by_username(self, username: str) -> dict:
        """Return the response from GitHub's /users/{username}/"""
        return self.api.users.get_by_username(username=username)

    def get_artifacts(self, owner="", repo_slug="", name=None):
        """Return a list of artifacts from the GH api.

        Filter results by the name of the artifact by supplying name.
        """
        owner = owner or self.owner
        repo_slug = repo_slug or self.repo_slug
        url = f"https://api.github.com/repos/{owner}/{repo_slug}/actions/artifacts"
        params = {}
        if name:
            params["name"] = name
        headers = {"accept": "application/vnd.github+json"}
        response = requests.get(url, params=params, headers=headers)
        if response.status_code != 200:
            logger.error(
                "Error while fetching artifacts.", status_code=response.status_code
            )
            return
        data = response.json()
        return data

    def get_artifact_content(self, url):
        resp = requests.get(
            url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "accept": "application/vnd.github+json",
            },
        )
        if resp.status_code != 200:
            logger.error(
                "Error while fetching artifact file.", status_code=resp.status_code
            )
            return ""
        myzip = ZipFile(BytesIO(resp.content))
        with myzip.open(myzip.filelist[0]) as f:
            return f.read().decode()


class GithubDataParser:
    def get_commits_per_month(self, commits: list[dict]):
        """Get the number of commits per month from a list of commits.

        :param commits: List[Commit], list of commits.
        :return: Dict[str, datetime], dictionary mapping month-year dates to commit
        counts.
        """
        commit_counts = defaultdict(int)
        for commit in commits:
            date = parse(commit.commit.author.date)
            month_year = datetime(date.year, date.month, 1).date()
            commit_counts[month_year] += 1

        return dict(commit_counts)

    def parse_commit(self, commit_data: dict) -> dict:
        """Parse the commit data from Github and return a dict of the data we want."""
        published_at = commit_data["committer"]["date"]
        description = commit_data.get("message", "")
        github_url = commit_data["html_url"]
        release_date = datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ").date()
        return {
            "release_date": release_date,
            "description": description,
            "github_url": github_url,
            "data": obj2dict(commit_data),
        }

    def parse_gitmodules(self, gitmodules: str) -> dict:
        """Parse the .gitmodules file.
        Expects the multiline contents of https://github.com/boostorg/boost/.gitmodules
        to be passed in

        :param gitmodules: str, the .gitmodules file
        :return: dict, the parsed .gitmodules file
        """
        modules = []
        current_submodule = None

        submodule_re = re.compile(r"^\[submodule \"(.*)\"\]$")
        url_re = re.compile(r"^\s*url\s*\=\s*\.\.\/(.*)\.git\s*$")

        for line in gitmodules.split("\n"):
            sub_m = submodule_re.match(line)
            if sub_m:
                current_submodule = {"module": sub_m.group(1)}
                continue

            url_m = url_re.match(line)
            if url_m:
                name = url_m.group(1)
                current_submodule["url"] = name
                modules.append(current_submodule)
                current_submodule = None

        return modules

    def parse_libraries_json(self, libraries_json: dict) -> dict:
        """Parse the individual library metadata from 'meta/libraries.json'."""
        return {
            "name": libraries_json["name"],
            "key": libraries_json["key"],
            "authors": libraries_json.get("authors", []),
            "description": libraries_json.get("description", ""),
            "category": libraries_json.get("category", []),
            "maintainers": libraries_json.get("maintainers", []),
            "cxxstd": libraries_json.get("cxxstd"),
        }

    def parse_tag(self, tag_data: dict) -> dict:
        """Parse the tag data from Github and return a dict of the data we want."""
        published_at = tag_data.get("published_at", "")
        description = tag_data.get("body", "")
        github_url = tag_data.get("html_url", "")
        release_date = datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ").date()
        return {
            "release_date": release_date,
            "description": description,
            "github_url": github_url,
            "data": obj2dict(tag_data),
        }

    def extract_contributor_data(self, contributor: str) -> dict:
        """Takes an author/maintainer string and returns a dict with their data."""
        data = {}

        email = self.extract_email(contributor)
        if bool(email):
            data["email"] = email
            data["valid_email"] = True
        else:
            data["email"] = None
            data["valid_email"] = False

        data["display_name"] = self.extract_name(contributor)

        return data

    def extract_email(self, val: str) -> str:
        """
        Finds an email address in a string, reformats it, and returns it.
        Assumes the email address is in this format:
        <firstlast -at- domain.com>

        Does not raise errors.

        Includes as many catches for variants in the formatting as I found in a first
        pass.
        """
        result = re.search("<.+>", val)
        if result:
            raw_email = result.group()
            email = (
                raw_email.replace("-at-", "@")
                .replace("- at -", "@")
                .replace("-dot-", ".")
                .replace("<", "")
                .replace(">", "")
                .replace(" ", "")
                .replace("-underscore-", "_")
            )
            try:
                validate_email(email)
            except ValidationError as e:
                logger.info("Could not extract valid email", value=val, exc_msg=str(e))
                return
            return email

    def extract_name(self, val: str) -> str:
        email = re.search("<.+>", val)
        if email:
            val = val.replace(email.group(), "")

        return val.strip()
