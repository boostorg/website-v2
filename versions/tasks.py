import requests
import structlog

from config.celery import app
from django.conf import settings
from django.core.management import call_command
from fastcore.xtras import obj2dict
from core.githubhelper import GithubAPIClient, GithubDataParser
from libraries.github import LibraryUpdater
from libraries.models import Library, LibraryVersion
from libraries.tasks import get_and_store_library_version_documentation_urls_for_version
from libraries.utils import version_within_range
from versions.models import Version
from versions.releases import store_release_notes_for_version


logger = structlog.getLogger(__name__)


@app.task
def import_versions(delete_versions=False, new_versions_only=False, token=None):
    """Imports Boost release information from Github and updates the local database.

    The function retrieves Boost tags from the main Github repo, excluding beta releases
    and release candidates.

    It then creates or updates a Version instance in the local database for each tag.

    Args:
        delete_versions (bool): If True, deletes all existing Version instances before
            importing.
        new_versions_only (bool): If True, only imports versions that do not already
            exist in the database.
        token (str): Github API token, if you need to use something other than the
            setting.
    """
    if delete_versions:
        Version.objects.all().delete()
        logger.info("import_versions_deleted_all_versions")

    # Get all Boost tags from Github
    client = GithubAPIClient(token=token)
    tags = client.get_tags()

    for tag in tags:
        name = tag["name"]

        if skip_tag(name, new_versions_only):
            continue

        logger.info("import_versions_importing_version", version_name=name)
        import_version.delay(name, tag=tag, token=token)

    # Get all release notes
    import_release_notes.delay()


@app.task
def import_release_notes():
    """Imports release notes from the existing rendered
    release notes in the repository."""
    for version in Version.objects.active().filter(full_release=True):
        store_release_notes_task.delay(str(version.pk))


@app.task
def store_release_notes_task(version_pk):
    """Stores the release notes for a single version."""
    try:
        Version.objects.get(pk=version_pk)
    except Version.DoesNotExist:
        logger.error(
            "store_release_notes_task_version_does_not_exist", version_pk=version_pk
        )
        return
    store_release_notes_for_version(version_pk)


@app.task
def import_version(
    name,
    tag=None,
    token=None,
    beta=False,
    full_release=True,
    base_url="https://github.com/boostorg/boost/releases/tag/",
    get_release_date=True,
):
    """Imports a single Boost version from Github and updates the local
    database. Also runs import_release_downloads and import_library_versions
    for the version.

    base_url: Most base_url values will be for tags, but we do save some
    Version objects that are branches and not tags (mainly master and develop).
    """
    # Save the response we got from Github, if present
    if tag:
        data = obj2dict(tag)
    else:
        data = {}

    version, created = Version.objects.update_or_create(
        name=name,
        defaults={
            "github_url": f"{base_url}{name}",
            "beta": beta,
            "full_release": full_release,
            "data": data,
        },
    )

    if created:
        logger.info(
            "import_versions_created_version",
            version_name=name,
            version_id=version.pk,
        )
    else:
        logger.info(
            "import_versions_updated_version",
            version_name=name,
            version_id=version.pk,
        )

    # Get the release date for the version
    if get_release_date and not version.release_date:
        commit_sha = tag["commit"]["sha"]
        get_release_date_for_version.delay(version.pk, commit_sha, token=token)

    # Load release downloads
    import_release_downloads.delay(version.pk)

    # Load library-versions
    import_library_versions.delay(version.name, token=token)


@app.task
def import_development_versions():
    """Imports the `master` and `develop` branches as Versions"""
    branches = ["master", "develop"]
    base_url = "https://github.com/boostorg/boost/tree/"

    for branch in branches:
        import_version.delay(
            branch,
            branch,
            beta=False,
            full_release=False,
            get_release_date=False,
            base_url=base_url,
        )

        import_library_versions.delay(branch, version_type="branch")


@app.task
def import_most_recent_beta_release(token=None, delete_old=False):
    """Imports the most recent beta release from Github and updates the local database.
    Also runs import_release_downloads and import_library_versions for the version.

    Args:
        token (str): Github API token, if you need to use something other than the
            setting.
        delete_old (bool): If True, deletes all existing beta Version instances
            before importing.
    """
    if delete_old:
        Version.objects.filter(beta=True).delete()
        logger.info("import_most_recent_beta_release_deleted_all_versions")

    most_recent_version = Version.objects.most_recent()
    # Get all Boost tags from Github
    client = GithubAPIClient(token=token)
    tags = client.get_tags()

    for tag in tags:
        name = tag["name"]
        # Get the most recent beta version that is at least as recent as
        # the most recent stable version
        if "beta" in name and name >= most_recent_version.name:
            logger.info("import_most_recent_beta_release", version_name=name)
            import_version.delay(name, tag, token=token, beta=True, full_release=False)
            return


LIBRARY_KEY_EXCEPTIONS = {
    "utility/string_ref": [
        {
            "new_key": "utility/string_view",
            "new_name": "String View",
            "min_version": "boost-1.78.0",  # Apply change for versions >= boost-1.78.0
        }
    ],
}


@app.task
def import_library_versions(version_name, token=None, version_type="tag"):
    """For a specific version, imports all LibraryVersions using GitHub data"""
    try:
        version = Version.objects.get(name=version_name)
    except Version.DoesNotExist:
        logger.info(
            "import_library_versions_version_not_found", version_name=version_name
        )

    client = GithubAPIClient(token=token)
    updater = LibraryUpdater(client=client)
    parser = GithubDataParser()

    # Get the gitmodules file for the version, which contains library data
    # The master and develop branches are not tags, so we retrieve their data
    # from the heads/ namespace instead of tags/
    if version_type == "tag":
        ref = client.get_ref(ref=f"tags/{version_name}")
    else:
        ref = client.get_ref(ref=f"heads/{version_name}")

    raw_gitmodules = client.get_gitmodules(ref=ref)
    if not raw_gitmodules:
        logger.info(
            "import_library_versions_invalid_gitmodules", version_name=version_name
        )
        return

    gitmodules = parser.parse_gitmodules(raw_gitmodules.decode("utf-8"))

    # For each gitmodule, gets its libraries.json file and save the libraries
    # to the version
    for gitmodule in gitmodules:
        library_name = gitmodule["module"]
        if library_name in updater.skip_modules:
            continue

        try:
            libraries_json = client.get_libraries_json(
                repo_slug=library_name, tag=version_name
            )
        except (
            requests.exceptions.JSONDecodeError,
            requests.exceptions.HTTPError,
            Exception,
        ):
            # Can happen with older releases
            library_version = save_library_version_by_library_key(
                library_name, version, gitmodule
            )
            if library_version:
                logger.info(
                    "import_library_versions_by_library_key",
                    version_name=version_name,
                    library_name=library_name,
                )
            else:
                logger.info(
                    "import_library_versions_skipped_library",
                    version_name=version_name,
                    library_name=library_name,
                )
            continue

        if not libraries_json:
            # Can happen with older releases -- we try to catch all exceptions
            # so this is just in case
            logger.info(
                "import_library_versions_skipped_library",
                version_name=version_name,
                library_name=library_name,
            )
            continue

        libraries = (
            libraries_json if isinstance(libraries_json, list) else [libraries_json]
        )
        parsed_libraries = [parser.parse_libraries_json(lib) for lib in libraries]
        for lib_data in parsed_libraries:
            if lib_data["key"] in updater.skip_libraries:
                continue

            # Handle exceptions based on version and library key
            exceptions = LIBRARY_KEY_EXCEPTIONS.get(lib_data["key"], [])
            for exception in exceptions:
                if version_within_range(
                    version_name,
                    min_version=exception.get("min_version"),
                    max_version=exception.get("max_version"),
                ):
                    lib_data["key"] = exception["new_key"]
                    lib_data["name"] = exception.get("name", lib_data["name"])
                    break  # Stop checking exceptions if a match is found

            library, _ = Library.objects.get_or_create(
                key=lib_data["key"],
                defaults={
                    "name": lib_data.get("name"),
                    "description": lib_data.get("description"),
                    "cpp_standard_minimum": lib_data.get("cxxstd"),
                    "data": lib_data,
                },
            )
            library_version, _ = LibraryVersion.objects.update_or_create(
                version=version, library=library, defaults={"data": lib_data}
            )
            if not library.github_url:
                pass
            #     # todo: handle this. Need a github_url for these.

    # Retrieve and store the docs url for each library-version in this release
    get_and_store_library_version_documentation_urls_for_version.delay(version.pk)

    # Load maintainers for library-versions
    call_command("update_maintainers", "--release", version.name)


@app.task
def import_release_downloads(version_pk):
    version = Version.objects.get(pk=version_pk)
    version_num = version.name.replace("boost-", "")
    if version_num < "1.63.0":
        # Downloads are in Sourceforge for older versions, and that has
        # not been implemented yet
        logger.info("import_release_downloads_skipped", version_name=version.name)
        return

    call_command("import_artifactory_release_data", release=version_num)
    logger.info("import_release_downloads_complete", version_name=version.name)


@app.task
def get_release_date_for_version(version_pk, commit_sha, token=None):
    """
    Gets and stores the release date for a Boost version using the given commit SHA.

    :param version_pk: The primary key of the version to get the release date for.
    :param commit_sha: The SHA of the commit to get the release date for.
    """
    try:
        version = Version.objects.get(pk=version_pk)
    except Version.DoesNotExist:
        logger.error(
            "get_release_date_for_version_no_version_found", version_pk=version_pk
        )
        return

    if not token:
        token = settings.GITHUB_TOKEN

    parser = GithubDataParser()
    client = GithubAPIClient(token=token)

    try:
        commit = client.get_commit_by_sha(commit_sha=commit_sha)
    except Exception as e:
        logger.error(
            "get_release_date_for_version_failed",
            version_pk=version_pk,
            commit_sha=commit_sha,
            e=str(e),
        )
        return

    commit_data = parser.parse_commit(commit)
    release_date = commit_data.get("release_date")

    if release_date:
        version.release_date = release_date
        version.save()
        logger.info("get_release_date_for_version_success", version_pk=version_pk)
    else:
        logger.error("get_release_date_for_version_error", version_pk=version_pk)


# Helper functions


def save_library_version_by_library_key(library_key, version, gitmodule={}):
    """Saves a LibraryVersion instance by library key and version."""
    try:
        library = Library.objects.get(key=library_key)
        library_version, _ = LibraryVersion.objects.update_or_create(
            version=version, library=library, defaults={"data": gitmodule}
        )
        return library_version
    except Library.DoesNotExist:
        return


def skip_tag(name, new=False):
    """Returns True if the given tag should be skipped."""
    # Skip beta releases, release candidates, and pre-1.0 versions
    EXCLUSIONS = ["beta", "-rc"]

    # If we are only importing new versions, and we already have this one, skip
    if new and Version.objects.filter(name=name).exists():
        return True

    # If this version falls in our exclusion list, skip it
    if any(pattern in name.lower() for pattern in EXCLUSIONS):
        return True

    # If this version is too old, skip it
    version_num = name.replace("boost-", "")
    if version_num < settings.MINIMUM_BOOST_VERSION:
        return True

    return False
