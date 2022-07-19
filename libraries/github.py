import base64
import os
import itertools
import re
import structlog

from ghapi.all import GhApi, paged
from .models import Library

logger = structlog.get_logger()


def get_api():
    """
    Return an GH API object, using a GITHUB_TOKEN from the environment if it exists
    """
    token = os.environ.get("GITHUB_TOKEN", None)

    return GhApi(token=token)


def repo_ref(owner, repo, ref):
    api = get_api()


def repo_issues(owner, repo, state="all"):
    # Get all of our issue pages
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
    results = []
    for p in pages:
        results.extend(p)

    return results


def repo_prs(owner, repo, state="all"):
    # Get all of our PR pages
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
    logger.info("update_all_github_repos")


def parse_submodules(content):
    """Expects the multiline contents of https://github.com/boostorg/boost/.gitmodules to be passed in"""
    modules = []

    current_submodule = None

    submodule_re = re.compile(r"^\[submodule \"(.*)\"\]$")
    url_re = re.compile(r"^\s*url\s*\=\s*\.\.\/(.*)\.git\s*$")

    for line in content.split("\n"):
        print(line)
        sub_m = submodule_re.match(line)
        if sub_m:
            current_submodule = {"module": sub_m.group(1)}
            continue

        url_m = url_re.match(line)
        if url_m:
            name = url_m.group(1)
            current_submodule["url"] = name
            print(f"FOUND: {current_submodule}")
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

    def get_ref(self, repo, ref):
        """Get a particular ref of a particular repo"""
        return self.api.git.get_ref(owner=self.owner, repo=repo, ref=ref)

    def get_boost_ref(self):
        """Retrieve the latest commit to master for boostorg/boost repo"""
        return self.get_ref(repo="boost", ref="heads/master")

    def get_library_list(self):
        """Determine our list of libraries"""
        r = self.get_boost_ref()
        tree_sha = r["object"]["sha"]

        top_level_files = self.api.git.get_tree(
            owner=self.owner, repo="boost", tree_sha=tree_sha
        )
        gitmodules = None

        for item in top_level_files["tree"]:
            if item["path"] != ".gitmodules":
                continue
            file_sha = item["sha"]
            f = self.api.git.get_blob(owner=self.owner, repo="boost", file_sha=file_sha)
            return base64.b64decode(f["content"])


class GithubUpdater:
    """
    We will instantiate an instance of this class for each Library.  Running
    the `update()` method will update all Github related information we need
    for the site
    """

    def __init__(self, owner, repo):
        self.owner = owner
        self.repo = repo
        self.logger = logger.bind(owner=owner, repo=repo)

    def update(self):
        self.logger.info("update_github_repo")

        try:
            self.update_issues()
        except Exception:
            self.logger.exception("update_issues_error")

        try:
            self.update_prs()
        except Exception:
            self.logger.exception("update_prs_error")

    def update_issues(self):
        self.logger.info("updating_repo_issues")
        issues = repo_issues(self.owner, self.repo, state="all")

    def update_prs(self):
        self.logger.info("updating_repo_prs")
        raise ValueError("testing!")
