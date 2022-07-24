import base64
import os
import itertools
import re
import requests
import structlog

from ghapi.all import GhApi, paged
from .models import Library, Category

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
            gitmodules = base64.b64decode(f["content"])
            break

        modules = parse_submodules(gitmodules.decode("utf-8"))

        # Parse the modules into libraries.  Most libraries are individual
        # repositories, but a few such as "system", "functional", and others
        # contain multiple libraries
        libraries = []
        for m in modules:
            name = m["module"]

            if name in self.skip_modules:
                self.logger.info("skipping_library", skipped_library=name)
                continue

            meta = self.get_library_metadata(repo=name)
            github_url = f"https://github.com/boostorg/{name}/"
            if type(meta) is list:
                for sublibrary in meta:
                    libraries.append(
                        {
                            "name": name,
                            "github_url": github_url,
                            "authors": sublibrary["authors"],
                            "description": sublibrary["description"],
                            "category": sublibrary["category"],
                            "authors": sublibrary["authors"],
                            "maintainers": sublibrary.get("maintainers", []),
                            "cxxstd": sublibrary.get("cxxstd"),
                        }
                    )

            elif type(meta) is dict:
                libraries.append(
                    {
                        "name": name,
                        "github_url": github_url,
                        "authors": meta["authors"],
                        "description": meta["description"],
                        "category": meta["category"],
                        "authors": meta["authors"],
                        "maintainers": meta.get("maintainers", []),
                        "cxxstd": meta.get("cxxstd"),
                    }
                )

        return libraries

    def get_library_metadata(self, repo):
        """Retrieve library metadata from 'meta/libraries.json'"""
        url = f"https://raw.githubusercontent.com/{self.owner}/{repo}/develop/meta/libraries.json"
        try:
            r = requests.get(url)
            return r.json()
        except Exception as e:
            self.logger.exception("get_library_metadata_failed", repo=repo, url=url)
            return None

    def update_libraries(self):
        """Update all libraries and they metadata"""
        libs = self.get_library_list()

        self.logger.info("update_all_libraries_metadata", library_count=len(libs))

        for lib in libs:
            self.update_library(lib)

    def update_categories(self, obj, categories):
        """Update all of the categories for an object"""
        obj.categories.clear()
        for c in categories:
            cat, created = Category.objects.get_or_create(name=c)
            obj.categories.add(cat)

    def update_library(self, lib):
        """Update an individual library"""
        logger = self.logger.bind(lib=lib)
        try:
            obj, created = Library.objects.get_or_create(name=lib["name"])
            obj.github_url = lib["github_url"]
            obj.description = lib["description"]
            obj.cpp_standard_minimum = lib["cxxstd"]

            # Update categories
            self.update_categories(obj, categories=lib["category"])

            # Save any changes
            logger = logger.bind(obj_created=created)
            obj.save()

            logger.info("library_udpated")

        except Exception as e:
            logger.exception("library_update_failed")


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
