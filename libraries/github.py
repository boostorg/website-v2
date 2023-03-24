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


def get_api():
    """
    Return an GH API object, using a GITHUB_TOKEN from the environment if it exists
    """
    token = os.environ.get("GITHUB_TOKEN", None)

    return GhApi(token=token)


def get_user_by_username(username):
    """Return the response from GitHub's /users/{username}/"""
    api = get_api()
    return api.users.get_by_username(username=username)


def get_repo(api, owner, repo):
    """
    Return the response from GitHub's /repos/{owner}/{repo}
    """
    return api.repos.get(owner=owner, repo=repo)


def repo_issues(owner, repo, state="all", issues_only=True):
    """
    Get all issues for a repo.
    Note: The GitHub API considers both PRs and Issues to be "Issues" and does not
    support filtering in the request, so to exclude PRs from the list of issues, we
    do some manual filtering of the results
    Note: GhApi() returns results as AttrDict objects:
    https://fastcore.fast.ai/basics.html#attrdict
    """
    api = get_api()
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
    api = get_api()
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


def update_all_repos_info():
    """Update all of our repos information from github"""
    # FIXME: Write this function
    logger.info("update_all_github_repos")


def parse_submodules(content):
    """Expects the multiline contents of https://github.com/boostorg/boost/.gitmodules to be passed in"""
    modules = []

    current_submodule = None

    submodule_re = re.compile(r"^\[submodule \"(.*)\"\]$")
    url_re = re.compile(r"^\s*url\s*\=\s*\.\.\/(.*)\.git\s*$")

    for line in content.split("\n"):
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


class LibraryUpdater:
    """
    This class is used to sync Libraries from the list of git submodules
    and their `libraries.json` file metadata.
    """

    def __init__(self, owner="boostorg"):
        self.api = get_api()
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

    def get_ref(self, repo, ref):
        """Get a particular ref of a particular repo"""
        return self.api.git.get_ref(owner=self.owner, repo=repo, ref=ref)

    def get_boost_ref(self):
        """Retrieve the latest commit to master for boostorg/boost repo"""
        return self.get_ref(repo="boost", ref="heads/master")

    def get_library_list(self):
        """
        Determine our list of libraries from .gitmodules and sub-repo
        libraries.json files
        """
        # Find our latest .gitmodules
        ref = self.get_boost_ref()
        tree_sha = ref["object"]["sha"]

        # Get all the top-level elements of the main Boost repo
        top_level_files = self.api.git.get_tree(
            owner=self.owner, repo="boost", tree_sha=tree_sha
        )
        gitmodules = None

        # Cycle through each top-level item
        for item in top_level_files["tree"]:
            # We're only looking for the `.gitmodules` file, so skip everything else
            if item["path"] != ".gitmodules":
                continue
            file_sha = item["sha"]
            f = self.api.git.get_blob(owner=self.owner, repo="boost", file_sha=file_sha)
            gitmodules = base64.b64decode(f["content"])
            break

        # Parse the content of the .gitmodules file into a list of dicts with the info we need
        modules = parse_submodules(gitmodules.decode("utf-8"))

        # Parse the module data into libraries.  Most libraries are individual
        # repositories, but a few such as "system", "functional", and others
        # contain multiple libraries
        libraries = []
        for m in modules:
            name = m["module"]

            if name in self.skip_modules:
                self.logger.info("skipping_library", skipped_library=name)
                continue

            libraries_json = self.get_libraries_json(repo=name)
            github_data = self.get_library_github_data(owner=self.owner, repo=name)
            last_github_update = parse_date(github_data.get("updated_at", ""))

            if type(libraries_json) is list:
                for library in libraries_json:
                    libraries.append(
                        {
                            "name": library["name"],
                            "key": library["key"],
                            "github_url": github_data.get("html_url", ""),
                            "authors": library.get("authors", ""),
                            "description": library.get("description", ""),
                            "category": library.get("category", ""),
                            "maintainers": library.get("maintainers", []),
                            "cxxstd": library.get("cxxstd"),
                            "last_github_update": last_github_update,
                        }
                    )

            elif type(libraries_json) is dict:
                libraries.append(
                    {
                        "name": libraries_json["name"],
                        "key": libraries_json["key"],
                        "github_url": github_data.get("html_url", ""),
                        "authors": libraries_json.get("authors", ""),
                        "description": libraries_json.get("description", ""),
                        "category": libraries_json.get("category", ""),
                        "maintainers": libraries_json.get("maintainers", []),
                        "cxxstd": libraries_json.get("cxxstd"),
                        "last_github_update": last_github_update,
                    }
                )

        return libraries

    def get_libraries_json(self, repo):
        """
        Retrieve library metadata from 'meta/libraries.json'
        Each Boost library will have a `meta` directory with a `libraries.json` file.
        Example: https://github.com/boostorg/align/blob/5ad7df63cd792fbdb801d600b93cad1a432f0151/meta/libraries.json
        """
        url = f"https://raw.githubusercontent.com/{self.owner}/{repo}/develop/meta/libraries.json"

        try:
            response = requests.get(url)
            return response.json()
        except Exception:
            self.logger.exception("get_library_metadata_failed", repo=repo, url=url)
            return None

    def get_library_github_data(self, owner, repo):
        """
        Retrieve other data about the library from the GitHub API
        """
        response = get_repo(self.api, owner, repo)
        return response

    def update_libraries(self):
        """Update all libraries with the metadata"""
        libs = self.get_library_list()

        self.logger.info("update_all_libraries_metadata", library_count=len(libs))

        for lib in libs:
            library = self.update_library(lib)
            github_updater = GithubUpdater(owner=self.owner, library=library)
            github_updater.update()

    def update_categories(self, obj, categories):
        """Update all of the categories for an object"""

        obj.categories.clear()
        for cat_name in categories:
            cat, created = Category.objects.get_or_create(name=cat_name)
            obj.categories.add(cat)

    def update_library(self, lib):
        """Update an individual library"""
        logger = self.logger.bind(lib=lib)
        try:
            obj, created = Library.objects.update_or_create(name=lib["name"])
            obj.github_url = lib["github_url"]
            obj.description = lib["description"]
            obj.cpp_standard_minimum = lib["cxxstd"]
            obj.last_github_update = lib["last_github_update"]

            # Update categories
            self.update_categories(obj, categories=lib["category"])

            # Save any changes
            logger = logger.bind(obj_created=created)
            obj.save()

            logger.info("library_udpated")

            return obj

        except Exception:
            logger.exception("library_update_failed")


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