import base64
import os
import re
import requests
import structlog

from fastcore.xtras import obj2dict
from ghapi.all import GhApi, paged

from .models import Category, Issue, Library, PullRequest
from .utils import parse_date

logger = structlog.get_logger()


class GithubAPIClient:
    """ A class to interact with the GitHub API. """
    def __init__(
        self,
        owner: str = "boostorg",
        ref: str = "heads/master",
        repo_slug: str = "boost",
    ) -> None:
        """
        Initialize the GitHubAPIClient.

        :param owner: str, the repository owner
        :param ref: str, the Git reference
        :param repo_slug: str, the repository slug
        """
        self.api = self.initialize_api()
        self.owner = owner
        self.ref = ref
        self.repo_slug = repo_slug

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
        if token is None:
            raise ValueError("GITHUB_TOKEN environment variable not found.")
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

    def get_gitmodules(self, repo_slug: str = None) -> str:
        """
        Get the .gitmodules file from the GitHub API.

        :param repo_slug: str, the repository slug
        :return: str, the .gitmodules file
        """
        if not repo_slug:
            repo_slug = self.repo_slug

        ref = self.get_ref()
        tree_sha = ref["object"]["sha"]
        tree = self.get_tree(tree_sha=tree_sha)

        gitmodules = None
        for item in tree["tree"]:
            if item["path"] == ".gitmodules":
                file_sha = item["sha"]
                blob = self.get_blob(repo_slug=repo_slug, file_sha=file_sha)
                return base64.b64decode(blob["content"])

    def get_libraries_json(self, repo_slug: str):
        """
        Retrieve library metadata from 'meta/libraries.json'
        Each Boost library will have a `meta` directory with a `libraries.json` file.
        Example: https://github.com/boostorg/align/blob/5ad7df63cd792fbdb801d600b93cad1a432f0151/meta/libraries.json
        """
        url = f"https://raw.githubusercontent.com/{self.owner}/{repo_slug}/develop/meta/libraries.json"

        try:
            response = requests.get(url)
            return response.json()
        except Exception:
            self.logger.exception("get_library_metadata_failed", repo=repo_slug, url=url)
            return None

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


class GithubDataParser:
    def parse_gitmodules(self, gitmodules: str) -> dict:
        """
        Parse the .gitmodules file.
        Expects the multiline contents of https://github.com/boostorg/boost/.gitmodules to be passed in

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
        """
        Parse the individual library metadata from 'meta/libraries.json'
        """
        return {
            "name": libraries_json["name"],
            "key": libraries_json["key"],
            "authors": libraries_json.get("authors", ""),
            "description": libraries_json.get("description", ""),
            "category": libraries_json.get("category", ""),
            "maintainers": libraries_json.get("maintainers", []),
            "cxxstd": libraries_json.get("cxxstd"),
        }



def get_user_by_username(username):
    """Return the response from GitHub's /users/{username}/"""
    api = GithubAPIClient().initialize_api()
    return api.users.get_by_username(username=username)


def repo_issues(owner, repo, state="all", issues_only=True):
    """
    Get all issues for a repo.
    Note: The GitHub API considers both PRs and Issues to be "Issues" and does not
    support filtering in the request, so to exclude PRs from the list of issues, we
    do some manual filtering of the results
    Note: GhApi() returns results as AttrDict objects:
    https://fastcore.fast.ai/basics.html#attrdict
    """
    api = GithubAPIClient().initialize_api()
    pages = list(
        paged(
            api.issues.list_for_repo,
            owner=owner,
            repo=repo,
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
        results = [result for result in all_results if not result.get("pull_request")]
    else:
        results = all_results

    return results


def repo_prs(owner, repo, state="all"):
    """
    Get all PRs for a repo
    Note: GhApi() returns results as AttrDict objects:
    https://fastcore.fast.ai/basics.html#attrdict
    """
    api = GithubAPIClient().initialize_api()
    pages = list(
        paged(
            api.pulls.list,
            owner=owner,
            repo=repo,
            state=state,
            per_page=100,
        )
    )
    # Concatenate all pages into a single list
    results = []
    for p in pages:
        results.extend(p)

    return results


class LibraryUpdater:
    """
    This class is used to sync Libraries from the list of git submodules
    and their `libraries.json` file metadata.
    """

    def __init__(self, owner="boostorg"):
        self.client = GithubAPIClient(owner=owner)
        self.api = self.client.initialize_api()
        self.parser = GithubDataParser()
        self.owner = owner
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

    def get_library_list(self):
        """
        Retrieve the full list of libraru data for Boost libraries from their Github repos. 

        Included libraries are rrtrieved from the list of modules in .gitmodules in the main Boost 
        repo. The libraries.json file is retrieved from each module and parsed to get the library
        metadata. Most libraries.json files contain information about individual libraries, but a few such as "system", "functional",
        and others contain multiple libraries.  
        """
        raw_gitmodules = self.client.get_gitmodules()
        gitmodules = self.parser.parse_gitmodules(raw_gitmodules.decode("utf-8"))

        libraries = []
        for gitmodule in gitmodules:
            if gitmodule["module"] in self.skip_modules:
                self.logger.info("skipping_library", skipped_library=gitmodule["module"])
                continue

            libraries_json = self.client.get_libraries_json(repo_slug=gitmodule["module"])
            github_data = self.client.get_repo(repo_slug=gitmodule["module"])
            extra_data = {"last_github_update": parse_date(github_data.get("updated_at", "")), "github_url": github_data.get("html_url", "")}

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
        library_data = self.get_library_list()

        self.logger.info("update_all_libraries_metadata", library_count=len(library_data))

        for library_data in library_data:
            library = self.update_library(library_data)
            # github_updater = GithubUpdater(owner=self.owner, library=library)
            # github_updater.update()

    def update_library(self, library_data):
        """Update an individual library"""
        logger = self.logger.bind(library=library_data)
        try:
            obj, created = Library.objects.update_or_create(
                key=library_data["key"], defaults={
                    "name": library_data["name"],
                    "key": library_data["key"], 
                    "github_url": library_data["github_url"], 
                    "description": library_data["description"],
                    "cpp_standard_minimum": library_data["cxxstd"], 
                    "last_github_update": library_data["last_github_update"]
            })

            # Update categories
            self.update_categories(obj, categories=library_data["category"])
            self.update_authors(obj, authors=library_data["authors"])
            self.update_maintainers(obj, maintainers=library_data["maintainers"])
            self.add_recent_library_version(obj)

            # Save any changes
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
            cat, created = Category.objects.get_or_create(name=cat_name)
            obj.categories.add(cat)

    def update_authors(self, obj, authors):
        pass

    def update_maintainers(self, obj, maintainers):
        pass

    def add_recent_library_version(self, obj):
        pass


class GithubUpdater:
    """
    We will instantiate an instance of this class for each Library.  Running
    the `update()` method will update all Github related information we need
    for the site
    """

    def __init__(self, owner="boostorg", library=None):
        self.owner = owner
        self.library = library
        self.logger = logger.bind(owner=owner, library=library)

    def update(self):
        self.logger.info("update_github_repo")

        # try:
        #     self.update_issues()
        # except Exception:
        #     self.logger.exception("update_issues_error")

        # try:
        #     self.update_prs()
        # except Exception:
        #     self.logger.exception("update_prs_error")

    def update_issues(self):
        """Update all issues for a library"""
        self.logger.info("updating_repo_issues")

        issues_data = repo_issues(
            self.owner, self.library.name, state="all", issues_only=True
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
                    library=self.library,
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
            except Exception as e:
                logger.exception(
                    "update_issues_error_skipped_issue",
                    issue_github_id=issue_dict.get("id"),
                    exc_msg=str(e),
                )
            logger.info(
                "issue_updated_successfully",
                issue_id=issue.id,
                created_issue=created,
                issue_github_id=issue.github_id,
            )

    def update_prs(self):
        """Update all PRs for a library"""
        self.logger.info("updating_repo_prs")

        prs_data = repo_prs(self.owner, self.library.name, state="all")

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
                    library=self.library,
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
            except Exception as e:
                logger.exception(
                    "update_prs_error_skipped_pr",
                    pr_github_id=pr_dict.get("id"),
                    exc_msg=str(e),
                )
            logger.info(
                "pull_request_updated_successfully",
                pr_id=pull_request.id,
                created_pr=created,
                pr_github_id=pull_request.github_id,
            )