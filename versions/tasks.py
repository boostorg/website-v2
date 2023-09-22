import structlog

from config.celery import app
from django.conf import settings
from django.core.management import call_command
from fastcore.xtras import obj2dict
from core.githubhelper import GithubAPIClient, GithubDataParser
from versions.models import Version


logger = structlog.getLogger(__name__)


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

    # Base url to generate the GitHub release URL
    BASE_URL = "https://github.com/boostorg/boost/releases/tag/"

    # Get all Boost tags from Github
    client = GithubAPIClient(token=token)
    tags = client.get_tags()

    for tag in tags:
        name = tag["name"]

        if skip_tag(name, new_versions_only):
            continue

        logger.info("import_versions_importing_version", version_name=name)
        version, created = Version.objects.update_or_create(
            name=name,
            defaults={"github_url": f"{BASE_URL}/{name}", "data": obj2dict(tag)},
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
        if not version.release_date:
            commit_sha = tag["commit"]["sha"]
            get_release_date_for_version.delay(version.pk, commit_sha, token=token)

        # Load release downloads
        import_release_downloads.delay(version.pk)


@app.task
def import_release_downloads(version_pk):
    version = Version.objects.get(pk=version_pk)
    version_num = version.name.replace("boost-", "")
    if version_num < "1.63.0":
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
