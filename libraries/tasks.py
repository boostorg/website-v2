import structlog
from dateutil.relativedelta import relativedelta

from config.celery import app
from django.db.models import Q
from django.utils import timezone
from core.boostrenderer import get_content_from_s3
from core.htmlhelper import get_library_documentation_urls
from libraries.github import LibraryUpdater
from libraries.models import LibraryVersion
from versions.models import Version
from .constants import (
    LIBRARY_DOCS_EXCEPTIONS,
    LIBRARY_DOCS_MISSING,
    VERSION_DOCS_MISSING,
)
from .utils import version_within_range

logger = structlog.getLogger(__name__)


@app.task
def update_library_version_documentation_urls_all_versions():
    """Run the task to update all documentation URLs for all versions"""
    for version in Version.objects.all().order_by("-name"):
        get_and_store_library_version_documentation_urls_for_version(version.pk)


@app.task
def get_and_store_library_version_documentation_urls_for_version(version_pk):
    """
    Store the url paths to the documentation for each library in a given version.
    The url paths are retrieved from the `libraries.htm` file in the docs stored in
    S3 for the given version.

    Retrieve the libraries from the "Libraries Listed Alphabetically" section of the
    HTML file. Loop through the unordered list of libraries and save the url path
    to the docs for that library to the database.

    Background: There are enough small exceptions to how the paths to the docs for each
    library are generated, so the easiest thing to do is to access the list of libraries
    for a particular release, scrape the url paths to their docs, and save those to the
    database.
    """
    try:
        version = Version.objects.get(pk=version_pk)
    except Version.DoesNotExist:
        raise

    if version_missing_docs(version):
        # If we know the docs for this version are missing, update related records
        LibraryVersion.objects.filter(version=version, missing_docs=False).update(
            missing_docs=True
        )
        return

    base_path = f"doc/libs/{version.boost_url_slug}/libs/"
    key = f"{base_path}libraries.htm"
    result = get_content_from_s3(key)

    if not result:
        raise ValueError(f"Could not get content from S3 for {key}")

    content = result["content"]
    library_tags = get_library_documentation_urls(content)
    library_versions = LibraryVersion.objects.filter(version=version)

    for library_name, url_path in library_tags:
        try:
            # In most cases, the name matches close enough to get the correct object
            library_version = library_versions.get(library__name__iexact=library_name)
            library_version.documentation_url = f"/{base_path}{url_path}"
            library_version.save()
        except LibraryVersion.DoesNotExist:
            logger.info(
                "get_library_version_documentation_urls_version_does_not_exist",
                library_name=library_name,
                version_slug=version.slug,
            )
            continue
        except LibraryVersion.MultipleObjectsReturned:
            logger.info(
                "get_library_version_documentation_urls_multiple_objects_returned",
                library_name=library_name,
                version_slug=version.slug,
            )
            continue

    # See if we can load missing docs URLS another way
    library_versions = (
        LibraryVersion.objects.filter(missing_docs=False)
        .filter(version=version)
        .filter(Q(documentation_url="") | Q(documentation_url__isnull=True))
    )
    for library_version in library_versions:
        # Check whether we know this library-version doesn't have docs
        if library_version_missing_docs(library_version):
            # Record that the docs are missing, since we know they are
            library_version.missing_docs = True
            library_version.save()
            continue

        # Check whether this library-version stores its docs in another location
        exceptions = LIBRARY_DOCS_EXCEPTIONS.get(library_version.library.slug, [])
        documentation_url = None
        for exception in exceptions:
            if version_within_range(
                library_version.version.boost_url_slug,
                min_version=exception.get("min_version"),
                max_version=exception.get("max_version"),
            ):
                exception_url_generator = exception["generator"]
                # Some libs use slugs that don't conform to what we generate via slugify
                slug = exception.get(
                    "alternate_slug",
                    library_version.library.slug.lower().replace("-", "_"),
                )
                documentation_url = exception_url_generator(
                    version.boost_url_slug,
                    slug,
                )
                break  # Stop looking once a matching version is found

        if documentation_url:
            # validate this in S3
            key = documentation_url.split("#")
            content = get_content_from_s3(key[0])
            if content:
                library_version.documentation_url = documentation_url
                library_version.save()
            else:
                logger.info(f"No valid docs in S3 for key {documentation_url}")


def version_missing_docs(version):
    """Returns True if we know the docs for this release are missing

    In this module to avoid a circular import"""
    # Check if the version is called out in VERSION_DOCS_MISSING
    if version.name in VERSION_DOCS_MISSING:
        return True

    # Check if the version is older than our oldest version
    # stored in S3
    if version_within_range(version.name, max_version="boost-1.30.0"):
        return True

    return False


def library_version_missing_docs(library_version):
    """Returns True if we know the docs for this lib-version
    are missing

    In this module to avoid a circular import
    """
    if library_version.missing_docs:
        return True

    missing_docs = LIBRARY_DOCS_MISSING.get(library_version.library.slug, [])
    version_name = library_version.version.name
    for entry in missing_docs:
        # Check if version is within specified range
        if version_within_range(
            version=version_name,
            min_version=entry.get("min_version"),
            max_version=entry.get("max_version"),
        ):
            return True
    return False


@app.task
def update_libraries():
    """Update local libraries from GitHub Boost libraries.

    Use the LibraryUpdater, which retrieves the active boost libraries from the
    Boost GitHub repo, to update the models with the latest information on that
    library (repo) along with its issues, pull requests, and related objects
    from GitHub.
    """
    updater = LibraryUpdater()
    updater.update_libraries()
    logger.info("libraries_tasks_update_all_libraries_finished")


@app.task
def update_commit_counts(token=None):
    """Imports commit counts for all libraries, broken down by month, and saves
    them to the database. See LibraryUpdater class for defaults.
    """
    updater = LibraryUpdater(token=token)
    updater.update_monthly_commit_counts()
    logger.info("libraries_update_commit_counts_finished")


@app.task
def update_current_month_commit_counts(token=None):
    """Imports commit counts for all libraries for the current month."""
    updater = LibraryUpdater(token=token)
    now = timezone.now()
    # First of this month
    since = timezone.make_aware(
        timezone.datetime(year=now.year, month=now.month, day=1)
    ) - relativedelta(days=1)
    updater.update_monthly_commit_counts(since=since, until=now)
    logger.info("libraries_update_current_month_commit_counts_finished")
