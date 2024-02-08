import structlog

from config.celery import app
from django.db.models import Q
from core.boostrenderer import get_content_from_s3
from core.htmlhelper import get_library_documentation_urls
from libraries.github import LibraryUpdater
from libraries.models import LibraryVersion
from libraries.utils import get_first_last_day_last_month
from versions.models import Version
from .utils import (
    generate_library_docs_url,
    generate_library_docs_url_v2,
    generate_library_docs_url_v3,
    generate_library_docs_url_v4,
    generate_library_docs_url_call_traits,
    generate_library_docs_url_dynamic_bitset,
    generate_library_docs_url_string_ref,
    generate_library_docs_url_string_view,
    version_within_range,
)

logger = structlog.getLogger(__name__)


LIBRARY_DOCS_EXCEPTIONS = {
    "any": [
        {
            "generator": generate_library_docs_url_v4,
            "min_version": "boost_1_29_0",
            "max_version": "boost_1_33_0",
        }
    ],
    "call-traits": [
        {
            "generator": generate_library_docs_url_call_traits,
            "max_version": "boost_1_60_0",
        }
    ],
    "circular-buffer": [
        {
            "generator": generate_library_docs_url_v4,
            "max_version": "boost_1_60_0",
        }
    ],
    "date-time": [
        {
            "generator": generate_library_docs_url_v4,
            "max_version": "boost_1_60_0",
        }
    ],
    "detail": [{"generator": generate_library_docs_url}],
    "dynamic-bitset": [
        {
            "generator": generate_library_docs_url_dynamic_bitset,
            "max_version": "boost_1_60_0",
        }
    ],
    "interprocess": [
        {"generator": generate_library_docs_url_v4, "max_version": "boost_1_47_0"}
    ],
    "intrusive": [
        {"generator": generate_library_docs_url_v4, "max_version": "boost_1_47_0"}
    ],
    "io": [
        {"generator": generate_library_docs_url_v2, "min_version": "boost_1_73_0"},
        {
            "generator": generate_library_docs_url_v3,
            "min_version": "boost_1_64_0",
            "max_version": "boost_1_72_0",
        },
    ],
    "program-options": [
        {"generator": generate_library_docs_url_v4, "max_version": "boost_1_60_0"}
    ],
    "string-algo": [
        {"generator": generate_library_docs_url_v4, "max_version": "boost_1_60_0"}
    ],
    "string-ref": [
        {
            "generator": generate_library_docs_url_string_ref,
            "max_version": "boost_1_77_0",
        }
    ],
    "string-view": [
        {
            "generator": generate_library_docs_url_string_view,
            "max_version": "boost_1_83_0",
        }
    ],
    "type-traits": [
        {"generator": generate_library_docs_url, "max_version": "boost_1_60_0"}
    ],
    "winapi": [{"generator": generate_library_docs_url}],
}


@app.task
def update_library_version_documentation_urls_all_versions():
    """Run the task to update all documentation URLs for all versions"""
    for version in Version.objects.all():
        get_and_store_library_version_documentation_urls_for_version.delay(version.pk)


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
    library_versions = LibraryVersion.objects.filter(version=version).filter(
        Q(documentation_url="") | Q(documentation_url__isnull=True)
    )
    for library_version in library_versions:
        exceptions = LIBRARY_DOCS_EXCEPTIONS.get(library_version.library.slug, [])
        documentation_url = None
        for exception in exceptions:
            if version_within_range(
                library_version.version.boost_url_slug,
                min_version=exception.get("min_version"),
                max_version=exception.get("max_version"),
            ):
                exception_url_generator = exception["generator"]
                documentation_url = exception_url_generator(
                    version.boost_url_slug,
                    library_version.library.slug.lower().replace("-", "_"),
                )
                break  # Stop looking once a matching version is found

        if documentation_url:
            # validate this in S3
            content = get_content_from_s3(documentation_url)
            if content:
                library_version.documentation_url = documentation_url
                library_version.save()
            else:
                logger.info(f"No valid docs in S3 for key {documentation_url}")


@app.task
def update_libraries(update_all=False):
    """Update local libraries from GitHub Boost libraries.

    Use the LibraryUpdater, which retrieves the active boost libraries from the
    Boost GitHub repo, to update the models with the latest information on that
    library (repo) along with its issues, pull requests, and related objects
    from GitHub.
    """
    updater = LibraryUpdater()
    if update_all:
        updater.update_libraries()
        logger.info("libraries_tasks_update_all_libraries_finished")
    else:
        since, until = get_first_last_day_last_month()
        updater.update_libraries(since=since, until=until)
        logger.info("libraries_tasks_update_libraries_finished")
