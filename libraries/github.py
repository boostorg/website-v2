import base64
import os
import re
from collections import defaultdict
from datetime import datetime
from dateutil.parser import parse
import requests
import structlog
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from fastcore.xtras import obj2dict
from ghapi.all import GhApi, paged


from .models import Category, Issue, Library, PullRequest
from .utils import generate_fake_email, parse_date

logger = structlog.get_logger()

User = get_user_model()


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
        self.api = self.initialize_api(token=token)
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

    def initialize_api(self, token=None) -> GhApi:
        """
        Initialize the GitHub API with the token from the environment variable.

        :return: GhApi, the GitHub API
        """
        if token is None:
            token = os.environ.get("GITHUB_TOKEN", None)
        return GhApi(token=token)

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
            self.logger.exception("get_all_commits_failed", repo=repo_slug, msg=str(e))
            return []

        return all_commits

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
        tree = self.get_tree(tree_sha=tree_sha)

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
            self.logger.exception(
                "get_library_metadata_failed", repo=repo_slug, url=url
            )
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
        return self.api.git.get_ref(owner=self.owner, repo=repo_slug, ref=ref)

    def get_repo(self, repo_slug: str = None) -> dict:
        """
        Get the repository from the GitHub API.

        :param repo_slug: str, the repository slug
        :return: dict, the repository
        """
        if not repo_slug:
            repo_slug = self.repo_slug
        return self.api.repos.get(owner=self.owner, repo=repo_slug)

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
            paged(
                self.api.issues.list_for_repo,
                owner=self.owner,
                repo=repo_slug,
                state=state,
                per_page=100,
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

    def get_tag_by_name(self, tag_name: str, repo_slug: str = None) -> dict:
        """Get a tag by name from the GitHub API."""
        if not repo_slug:
            repo_slug = self.repo_slug
        try:
            return self.api.repos.get_release_by_tag(
                owner=self.owner, repo=repo_slug, tag=tag_name
            )
        except Exception:
            logger.info("tag_not_found", tag_name=tag_name, repo_slug=repo_slug)
            return

    def get_tags(self, repo_slug: str = None) -> dict:
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

        first_name, last_name = self.extract_names(contributor)
        data["first_name"], data["last_name"] = first_name[:30], last_name[:30]

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

    def extract_names(self, val: str) -> list:
        """
        Returns a list of first, last names for the val argument.

        NOTE: This is an overly simplistic solution to importing names.
        Names that don't conform neatly to "First Last" formats will need
        to be cleaned up manually.
        """
        # Strip the email, if present
        email = re.search("<.+>", val)
        if email:
            val = val.replace(email.group(), "")

        names = val.strip().rsplit(" ", 1)

        if len(names) == 1:
            names.append("")

        return names


class LibraryUpdater:
    """
    This class is used to sync Libraries from the list of git submodules
    and their `libraries.json` file metadata.
    """

    def __init__(self, client=None):
        if client:
            self.client = client
        else:
            self.client = GithubAPIClient()
        self.api = self.client.initialize_api()
        self.parser = GithubDataParser()
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

    def get_library_list(self, gitmodules=None):
        """
        Retrieve the full list of library data for Boost libraries from their Github
        repos.

        Included libraries are rrtrieved from the list of modules in .gitmodules in the
        main Boost repo. The libraries.json file is retrieved from each module and
        parsed to get the library metadata. Most libraries.json files contain info
        about individual libraries, but a few such as "system", "functional", etc.
        contain multiple libraries.
        """
        libraries = []
        for gitmodule in gitmodules:
            if gitmodule["module"] in self.skip_modules:
                self.logger.info(
                    "skipping_library", skipped_library=gitmodule["module"]
                )
                continue

            libraries_json = self.client.get_libraries_json(
                repo_slug=gitmodule["module"]
            )
            github_data = self.client.get_repo(repo_slug=gitmodule["module"])
            extra_data = {
                "last_github_update": parse_date(github_data.get("updated_at", "")),
                "github_url": github_data.get("html_url", ""),
            }

            if type(libraries_json) is list:
                for library in libraries_json:
                    data = self.parser.parse_libraries_json(library)
                    libraries.append({**data, **extra_data})

            elif type(libraries_json) is dict:
                data = self.parser.parse_libraries_json(libraries_json)
                libraries.append({**data, **extra_data})

        return libraries

    def update_libraries(self):
        """Update all libraries with the metadata"""
        raw_gitmodules = self.client.get_gitmodules()
        gitmodules = self.parser.parse_gitmodules(raw_gitmodules.decode("utf-8"))
        library_data = self.get_library_list(gitmodules=gitmodules)

        self.logger.info(
            "update_all_libraries_metadata", library_count=len(library_data)
        )

        for lib in library_data:
            obj = self.update_library(lib)
            if not obj:
                continue
            self.update_categories(obj, categories=lib["category"])
            self.update_authors(obj, authors=lib["authors"])
            self.update_monthly_commit_counts(obj)
            self.update_issues(obj)
            self.update_prs(obj)

            if not obj.first_github_tag_date:
                self.update_first_github_tag_date(obj)

    def update_library(self, library_data: dict) -> Library:
        """Update an individual library"""
        logger = self.logger.bind(library=library_data)
        try:
            obj, created = Library.objects.update_or_create(
                key=library_data["key"],
                defaults={
                    "name": library_data["name"],
                    "github_url": library_data["github_url"],
                    "description": library_data["description"],
                    "cpp_standard_minimum": library_data["cxxstd"],
                    "last_github_update": library_data["last_github_update"],
                },
            )

            logger = logger.bind(obj_created=created)
            obj.save()
            logger.info("library_udpated")
            return obj

        except Exception:
            logger.exception("library_update_failed")

    def update_categories(self, obj, categories):
        """Update all of the categories for an object"""

        obj.categories.clear()
        for cat_name in categories:
            cat, _ = Category.objects.get_or_create(name=cat_name)
            obj.categories.add(cat)

    def update_authors(self, obj, authors=None):
        """
        Receives a list of strings from the libraries.json of a Boost library, and
        an object with an "authors" attribute.

        Processes that string into a User object that is added as an
        Author to the Library.
        """
        if not authors:
            return obj

        for author in authors:
            person_data = self.parser.extract_contributor_data(author)
            user = User.objects.find_contributor(
                email=person_data["email"],
                first_name=person_data["first_name"],
                last_name=person_data["last_name"],
            )

            if not user:
                email = person_data.pop("email")
                if not email:
                    email = generate_fake_email(
                        f"{person_data['first_name']} {person_data['last_name']}"
                    )
                user = User.objects.create_stub_user(email.lower(), **person_data)
                self.logger.info(f"User {user.email} created.")

            obj.authors.add(user)

        return obj

    def update_first_github_tag_date(self, obj):
        """
        Update the date of the first tag for a library
        """
        first_tag = self.client.get_first_tag(repo_slug=obj.github_repo)
        if first_tag:
            _, first_github_tag_date = first_tag
            obj.first_github_tag_date = parse_date(first_github_tag_date)
            obj.save()
            self.logger.info("lib_first_release_updated", obj_id=obj.id)

    def update_maintainers(self, obj, maintainers=None):
        """
        Receives a list of strings from the libraries.json of a Boost library, and
        an object with a M2M "maintainers" attribute.

        Processes the list of strings into User objects and adds them as Maintainers
        to the object.
        """
        if not maintainers:
            return

        for maintainer in maintainers:
            person_data = self.parser.extract_contributor_data(maintainer)
            user = User.objects.find_contributor(
                email=person_data["email"],
                first_name=person_data["first_name"],
                last_name=person_data["last_name"],
            )

            if not user:
                email = person_data.pop("email")
                if not email:
                    email = generate_fake_email(
                        f"{person_data['first_name']} {person_data['last_name']}"
                    )
                user = User.objects.create_stub_user(email.lower(), **person_data)
                self.logger.info(f"User {user.email} created.")

            obj.maintainers.add(user)
            self.logger.info(f"User {user.email} added as a maintainer of {obj}")

    def update_monthly_commit_counts(
        self, obj: Library, branch: str = "master", since=None, until=None
    ):
        """Update the monthly commit data for a library.

        :param obj: Library object
        :param commit_data: Dictionary of commit data, as output by the parser's
            get_commits_per_month method.
        :param branch: Branch to update commit data for. Defaults to "master".

        Note: Overrides CommitData objects for the library; does not increment
        the count.
        """
        self.logger.info("updating_monthly_commit_data")
        commits = self.client.get_commits(
            repo_slug=obj.github_repo, branch=branch, since=since, until=until
        )
        commit_data = self.parser.get_commits_per_month(commits)

        for month_year, commit_count in commit_data.items():
            data_obj, created = obj.commit_data.update_or_create(
                month_year=month_year,
                branch=branch,
                defaults={"commit_count": commit_count},
            )
            self.logger.info(
                "commit_data_updated",
                commit_data_pk=data_obj.pk,
                obj_created=created,
                library=obj.name,
                branch=branch,
            )

    def update_issues(self, obj):
        """Import GitHub issues for the library and update the database"""
        self.logger.info("updating_repo_issues")

        issues_data = self.client.get_repo_issues(
            self.client.owner, obj.github_repo, state="all", issues_only=True
        )
        for issue_dict in issues_data:
            # Get the date information
            closed_at = None
            created_at = None
            modified_at = None

            if issue_dict.get("closed_at"):
                closed_at = parse_date(issue_dict["closed_at"])

            if issue_dict.get("created_at"):
                created_at = parse_date(issue_dict["created_at"])

            if issue_dict.get("updated_at"):
                modified_at = parse_date(issue_dict["updated_at"])

            # Create or update the Issue object
            try:
                issue, created = Issue.objects.update_or_create(
                    library=obj,
                    github_id=issue_dict["id"],
                    defaults={
                        "title": issue_dict["title"][:255],
                        "number": issue_dict["number"],
                        "is_open": issue_dict["state"] == "open",
                        "closed": closed_at,
                        "created": created_at,
                        "modified": modified_at,
                        "data": obj2dict(issue_dict),
                    },
                )
                self.logger.info(
                    "issue_updated_successfully",
                    issue_id=issue.id,
                    created_issue=created,
                    issue_github_id=issue.github_id,
                )
            except Exception as e:
                self.logger.exception(
                    "update_issues_error_skipped_issue",
                    issue_github_id=issue_dict.get("id"),
                    exc_msg=str(e),
                )
                continue

    def update_prs(self, obj):
        """Update all PRs for a library"""
        self.logger.info("updating_repo_prs")

        prs_data = self.client.get_repo_prs(obj.github_repo, state="all")

        for pr_dict in prs_data:
            # Get the date information
            closed_at = None
            merged_at = None
            created_at = None
            modified_at = None

            if pr_dict.get("closed_at"):
                closed_at = parse_date(pr_dict["closed_at"])

            if pr_dict.get("merged_at"):
                merged_at = parse_date(pr_dict["merged_at"])

            if pr_dict.get("created_at"):
                created_at = parse_date(pr_dict["created_at"])

            if pr_dict.get("updated_at"):
                modified_at = parse_date(pr_dict["updated_at"])

            try:
                pull_request, created = PullRequest.objects.update_or_create(
                    library=obj,
                    github_id=pr_dict["id"],
                    defaults={
                        "title": pr_dict["title"][:255],
                        "number": pr_dict["number"],
                        "is_open": pr_dict["state"] == "open",
                        "closed": closed_at,
                        "merged": merged_at,
                        "created": created_at,
                        "modified": modified_at,
                        "data": obj2dict(pr_dict),
                    },
                )
                self.logger.info(
                    "pull_request_updated_successfully",
                    pr_id=pull_request.id,
                    created_pr=created,
                    pr_github_id=pull_request.github_id,
                )
            except Exception as e:
                self.logger.exception(
                    "update_prs_error_skipped_pr",
                    pr_github_id=pr_dict.get("id"),
                    exc_msg=str(e),
                )
