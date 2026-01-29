import re
import time
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import assert_never
from dateutil.relativedelta import relativedelta
import subprocess

import structlog
from ghapi.core import HTTP404NotFoundError
from fastcore.xtras import obj2dict

from django.db.models import Exists, OuterRef
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import dateparse, timezone

from versions.models import Version
from .constants import CATEGORY_OVERRIDES
from .models import (
    Category,
    Commit,
    CommitAuthor,
    CommitAuthorEmail,
    Issue,
    Library,
    LibraryVersion,
    PullRequest,
)
from core.githubhelper import GithubAPIClient, GithubDataParser

from .utils import generate_fake_email, parse_boostdep_artifact, parse_date

logger = structlog.get_logger()

User = get_user_model()


now = timezone.now()
FIRST_OF_MONTH_ONE_YEAR_AGO = timezone.make_aware(
    timezone.datetime(year=now.year - 1, month=now.month, day=1)
)
FIRST_OF_CURRENT_MONTH = timezone.make_aware(
    timezone.datetime(year=now.year, month=now.month, day=1)
) - relativedelta(days=1)


@dataclass
class ParsedCommit:
    email: str
    name: str
    message: str
    sha: str
    version: str
    is_merge: bool
    committed_at: timezone.datetime
    avatar_url: str | None = None


@dataclass
class VersionDiffStat:
    version: str
    files_changed: int
    insertions: int
    deletions: int


def get_commit_data_for_repo_versions(key, min_version=""):
    """Fetch commit data between minor versions (ignore patches).

    Get commits from one x.x.0 release to the next x.x.0 release. Commits
    to and from patches or beta versions are ignored.

    """
    library = Library.objects.get(key=key)
    parser = re.compile(
        r"^commit (?P<sha>\w+)(?:\n(?P<merge>Merge).*)?\nAuthor: (?P<name>[^\<]+)"
        r"\s+\<(?P<email>[^\>]+)\>\nDate:\s+(?P<date>.*)\n(?P<message>(.|\n)+?)"
        r"(?=(commit|\Z))",
        flags=re.MULTILINE,
    )
    re.compile(
        r"(?:(?P<files_changed>\d+) files changed)?.*?"
        r"(?:(?P<insertions>\d+) insertions)?.*?(?:(?P<deletions>\d+) deletions)?",
    )

    retry_count = 0
    with tempfile.TemporaryDirectory() as temp_dir:
        git_dir = Path(temp_dir) / f"{library.key}.git"
        is_clone_successful = False
        while retry_count < 5:
            retry_count += 1
            completed = subprocess.run(
                ["git", "clone", f"{library.github_url}.git", "--bare", str(git_dir)],
                capture_output=True,
            )
            message = completed.stdout.decode()
            error = completed.stderr.decode()
            # successful output always startswith 'Cloning into bare repository'
            # Clone message comes out from stderr, not stdout
            if not error.startswith("Cloning into bare repository"):
                logger.warning(
                    f"{completed.args} failed. Retrying git clone. Retry {retry_count}."
                )
                time.sleep(2**retry_count)
                continue
            else:
                is_clone_successful = True
                break
        if not is_clone_successful:
            logger.error(f"Clone failed for {library.key}. {message=} {error=}")
            return
        versions = (
            [""]
            + list(
                Version.objects.minor_versions()
                .filter(library_version__library__key=library.key)
                .order_by("version_array")
                .values_list("name", flat=True)
            )
            + ["master"]
        )
        for a, b in zip(versions, versions[1:]):
            if a < min_version and b < min_version:
                # Don't bother comparing two versions we don't care about
                continue
            shortstat = subprocess.run(
                ["git", "--git-dir", str(git_dir), "diff", f"{a}..{b}", "--shortstat"],
                capture_output=True,
            )
            stat_output = shortstat.stdout.decode()
            files_changed = insertions = deletions = 0
            if m := re.search(r"(\d+) files? changed", stat_output):
                files_changed = int(m.group(1))
            if m := re.search(r"(\d+) insertions?", stat_output):
                insertions = int(m.group(1))
            if m := re.search(r"(\d+) deletions?", stat_output):
                deletions = int(m.group(1))
            yield VersionDiffStat(
                version=b,
                insertions=insertions,
                deletions=deletions,
                files_changed=files_changed,
            )

            log_output = subprocess.run(
                ["git", "--git-dir", str(git_dir), "log", f"{a}..{b}", "--date", "iso"],
                capture_output=True,
            )
            commits = log_output.stdout.decode()
            for match in parser.finditer(commits):
                groups = match.groupdict()
                name = groups["name"].strip()
                email = groups["email"].strip()
                sha = groups["sha"].strip()
                is_merge = bool(groups.get("merge", False))
                message = groups["message"].strip("\n")
                message = "\n".join(
                    [m[4:] if m.startswith("    ") else m for m in message.split("\n")]
                )
                committed_at = dateparse.parse_datetime(groups["date"])
                assert committed_at  # should always exist
                yield ParsedCommit(
                    email=email,
                    name=name,
                    message=message,
                    sha=sha,
                    committed_at=committed_at,
                    is_merge=is_merge,
                    version=b,
                )


class LibraryUpdater:
    """
    This class is used to sync Libraries from the list of git submodules
    and their `libraries.json` file metadata.
    """

    def __init__(self, client=None, token=None):
        self.client = client or GithubAPIClient(token=token)
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
        # Libraries to skip that are not "modules", but appear as child-libraries
        # of other modules. Identified by the key used in the libraries.json file.
        self.skip_libraries = ["chrono/stopwatch"]

    def get_library_list(self, gitmodules):
        """
        Retrieve the full list of library data for Boost libraries from their Github
        repos.

        Included libraries are retrieved from the list of modules in .gitmodules in the
        main Boost repo. The libraries.json file is retrieved from each module and
        parsed to get the library metadata. Most libraries.json files contain info
        about individual libraries, but a few such as "system", "functional", etc.
        contain multiple libraries.
        """
        libraries = []
        for gitmodule in gitmodules:
            if gitmodule["module"] in self.skip_modules:
                continue

            libraries_json = self.client.get_libraries_json(
                repo_slug=gitmodule["module"]
            )
            github_data = self.client.get_repo(repo_slug=gitmodule["module"])
            extra_data = {
                "github_url": github_data.get("html_url", ""),
            }

            if type(libraries_json) is list:
                for library in libraries_json:
                    data = self.parser.parse_libraries_json(library)
                    if data["key"] in self.skip_libraries:
                        continue
                    libraries.append({**data, **extra_data})

            elif type(libraries_json) is dict:
                data = self.parser.parse_libraries_json(libraries_json)
                if data["key"] in self.skip_libraries:
                    continue
                libraries.append({**data, **extra_data})

        return libraries

    def update_libraries(self):
        """
        Update all libraries with the metadata from their libraries.json file.
        """
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
            # self.update_authors(obj, authors=lib["authors"])

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
                    "data": library_data,
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
            cat_name = CATEGORY_OVERRIDES.get(cat_name, cat_name)
            cat, _ = Category.objects.get_or_create(name=cat_name)
            obj.categories.add(cat)

    def update_authors(self, obj: Library | LibraryVersion, authors=None):
        """
        Receives a list of strings from the libraries.json of a Boost library
        or library_version, and an object with an "authors" attribute.

        Processes that string into a User object that is added as an
        Author to the Library or LibraryVersion.
        """
        if not authors:
            return obj

        if isinstance(authors, str):
            authors = [authors]
        for author in authors:
            person_data = self.parser.extract_contributor_data(author)
            email = person_data["email"]
            user = User.objects.find_contributor(
                email=person_data["email"],
                display_name=person_data["display_name"],
            )

            if not user:
                email = person_data.pop("email")
                if not email:
                    email = generate_fake_email(person_data["display_name"])
                    # With a new email, we may have a user record
                    user = User.objects.find_contributor(email=email)

            # If still no user, generate a fake one
            if not user:
                user = User.objects.create_stub_user(email.lower(), **person_data)
                self.logger.info(f"User {user.email} created.")

            obj.authors.add(user)

        return obj

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
                display_name=person_data["display_name"],
            )

            if not user:
                email = person_data.pop("email") or generate_fake_email(
                    person_data["display_name"]
                )
                if not (user := User.objects.filter(email=email).first()):
                    user = User.objects.create_stub_user(email.lower(), **person_data)
                    self.logger.info(f"User {user.email} created.")

            obj.maintainers.add(user)
            self.logger.info(f"User {user.email} added as a maintainer of {obj}")

    def update_issues(self, library):
        """Import GitHub issues for the library and update the database"""
        self.logger.info("updating_repo_issues")

        issues_data = self.client.get_repo_issues(
            self.client.owner, library.github_repo, state="all", issues_only=True
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
                    library=library,
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
                self.logger.debug(
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

    def update_prs(self, library: Library):
        """Update all PRs for a library"""
        self.logger.info("updating_repo_prs")

        prs_data = self.client.get_repo_prs(library.github_repo, state="all")

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
                    library=library,
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

    def update_commits(self, library: Library, clean=False, min_version=""):
        """Import a record of all commits between LibraryVersions."""
        authors = {}
        commits = []
        library_versions = {
            x.version.name: x
            for x in LibraryVersion.objects.filter(
                library=library, version__name__gte=min_version
            ).select_related("version")
        }
        library_version_updates = []

        def handle_commit(commit: ParsedCommit):
            author = authors.get(commit.email, None)
            if not author:
                if (
                    commit_author_email := CommitAuthorEmail.objects.filter(
                        email=commit.email,
                    )
                    .select_related("author")
                    .first()
                ):
                    author = commit_author_email.author
                else:
                    author = CommitAuthor.objects.create(
                        name=commit.name, avatar_url=commit.avatar_url
                    )
                    CommitAuthorEmail.objects.create(email=commit.email, author=author)
                authors[commit.email] = author

            try:
                library_version = library_versions[commit.version]
                return Commit(
                    author=author,
                    library_version=library_version,
                    sha=commit.sha,
                    message=commit.message,
                    committed_at=commit.committed_at,
                    is_merge=commit.is_merge,
                )

            except KeyError:
                return None

        def handle_version_diff_stat(diff: VersionDiffStat):
            try:
                lv = library_versions[diff.version]
            except KeyError:
                # we iterate over all library versions, but for libraries that
                #  haven't had updates in a release one may not exist for master/develop
                return None
            lv.insertions = diff.insertions
            lv.deletions = diff.deletions
            lv.files_changed = diff.files_changed
            return lv

        commits_handled = 0
        for item in get_commit_data_for_repo_versions(library.key, min_version):
            match item:
                case ParsedCommit():
                    commit_item = handle_commit(item)
                    if commit_item:
                        commits.append(commit_item)
                        commits_handled += 1
                case VersionDiffStat():
                    lv_update = handle_version_diff_stat(item)
                    if lv_update:
                        library_version_updates.append(lv_update)
                case _:
                    assert_never()

        with transaction.atomic():
            if clean:
                Commit.objects.filter(library_version__library=library).delete()
            Commit.objects.bulk_create(
                commits,
                update_conflicts=True,
                update_fields=["author", "message", "committed_at", "is_merge"],
                unique_fields=["library_version", "sha"],
            )
            LibraryVersion.objects.bulk_update(
                library_version_updates,
                ["insertions", "deletions", "files_changed"],
            )
        return commits_handled

    def update_commit_author_github_data(self, obj=None, email=None, overwrite=False):
        """Update CommitAuthor data by parsing data on their most recent commit."""
        if email:
            authors = CommitAuthor.objects.filter(
                Exists(CommitAuthorEmail.objects.filter(id=OuterRef("pk"), email=email))
            )
        elif obj:
            authors = CommitAuthor.objects.filter(
                Exists(
                    Library.objects.filter(
                        library_version__commit__author=OuterRef("id"),
                        pk=obj.pk,
                    )
                )
            )
        else:
            authors = CommitAuthor.objects.all()

        if not overwrite:
            authors = authors.filter(avatar_url=None)

        authors = (
            authors.annotate(
                most_recent_commit_sha=Commit.objects.filter(author=OuterRef("pk"))
                .order_by("-committed_at")
                .values("sha")[:1]
            )
            .annotate(
                most_recent_library_key=Library.objects.filter(
                    library_version__commit__sha=OuterRef("most_recent_commit_sha")
                ).values("key")[:1]
            )
            .filter(most_recent_library_key__isnull=False)
        )
        libraries = Library.objects.filter(
            key__in=[x.most_recent_library_key for x in authors]
        )
        repos = {x.key: x for x in libraries}
        for author in authors:
            try:
                commit = self.client.get_repo_ref(
                    repo_slug=repos[author.most_recent_library_key].github_repo,
                    ref=author.most_recent_commit_sha,
                )
            except HTTP404NotFoundError:
                self.logger.info(
                    f"Commit not found. Skipping avatar update for {author}."
                )
                continue
            if gh_author := commit["author"]:
                if gh_author["avatar_url"]:
                    author.avatar_url = gh_author["avatar_url"]
                if gh_author["html_url"]:
                    author.github_profile_url = gh_author["html_url"]
                author.save(update_fields=["avatar_url", "github_profile_url"])

    def fetch_most_recent_boost_dep_artifact_content(self, owner=""):
        # get artifacts with the name "boost-dep-artifact"
        artifacts = self.client.get_artifacts(
            owner=owner,
            repo_slug="website-v2",
            name="boost-dep-artifact",
        )
        if not artifacts or not artifacts.get("artifacts", None):
            logger.warning("No artifacts found.")
            return
        # get the most recent artifact
        artifact = artifacts["artifacts"][0]
        if artifact["expired"]:
            logger.error("The most recent boost-dep-artifact is expired.")
            return
        return self.client.get_artifact_content(artifact["archive_download_url"])

    def update_library_version_dependencies(self, owner="", clean=False):
        """Update LibraryVersion dependencies M2M via a github action artifact.

        owner: The repo owner. Defaults to `boostorg` in self.client.
        clean: Clear the M2M before adding dependencies.

        """
        saved_dependencies = 0
        saved_library_versions = 0

        content = self.fetch_most_recent_boost_dep_artifact_content(owner=owner)
        if not content:
            return
        for library_version, dependencies in parse_boostdep_artifact(content):
            if clean:
                library_version.dependencies.set(dependencies, clear=True)
            else:
                library_version.dependencies.add(*dependencies)
            saved_library_versions += 1
            saved_dependencies += len(dependencies)
        logger.info(
            "update_library_version_dependencies finished",
            saved_dependencies=saved_dependencies,
            saved_library_versions=saved_library_versions,
        )
