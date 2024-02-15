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
from .utils import (
    generate_library_docs_url,
    generate_library_docs_url_v2,
    generate_library_docs_url_v3,
    generate_library_docs_url_v4,
    generate_library_docs_url_bind_v1,
    generate_library_docs_url_bind_v2,
    generate_library_docs_url_math_v1,
    generate_library_docs_url_utility_v1,
    generate_library_docs_url_utility_v2,
    generate_library_docs_url_utility_v3,
    generate_library_docs_url_circular_buffer,
    generate_library_docs_url_core,
    generate_library_docs_url_double_nested_library_htm,
    generate_library_docs_url_double_nested_library_html,
    generate_library_docs_url_algorithm,
    generate_library_docs_url_numeric,
    generate_library_docs_url_numeric_2,
    generate_library_docs_url_string_ref,
    generate_library_docs_url_string_view,
    generate_library_docs_url_utility_anchor,
    generate_library_docs_url_throwexception,
    version_within_range,
)

logger = structlog.getLogger(__name__)


# Mapping for exeptions to loading URLs for older docs.
# key: Taken from Library.slug
# value: List of dictionaries with instructions for how to format docs URLs for
# those library-versions
#   - generator: function to use to generate the URL. Required.
#   - min_version: The earliest version that should use that generator. Optional.
#   - max_version: The most recent version that should use that generator. Optional.
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
            "generator": generate_library_docs_url_utility_v1,
            "max_version": "boost_1_60_0",
        }
    ],
    # Incomplete import
    "circular-buffer": [
        {
            "generator": generate_library_docs_url_v4,
            "max_version": "boost_1_60_0",
            "min_version": "boost_1_55_0",
        },
        {
            "generator": generate_library_docs_url_circular_buffer,
            "max_version": "boost_1_54_0",
        },
    ],
    "compressed-pair": [
        {
            "generator": generate_library_docs_url_utility_v1,
            "max_version": "boost_1_60_0",
        }
    ],
    "date-time": [
        {
            "generator": generate_library_docs_url_v4,
            "max_version": "boost_1_60_0",
        }
    ],
    # FIXME: Load correct path for 1.60.0 and prior
    "detail": [
        {
            "generator": generate_library_docs_url,
            "min_version": "boost_1_61_0",
        },
    ],
    "dynamic-bitset": [
        {
            "generator": generate_library_docs_url_double_nested_library_html,
            "max_version": "boost_1_60_0",
        }
    ],
    "enable-if": [
        {"generator": generate_library_docs_url_core, "max_version": "boost_1_60_0"}
    ],
    "function-types": [
        {"generator": generate_library_docs_url, "max_version": "boost_1_60_0"}
    ],
    "functionalhash": [
        {
            "generator": generate_library_docs_url_v4,
            "max_version": "boost_1_66_0",
            "alternate_slug": "hash",
        }
    ],
    "functionaloverloaded-function": [
        {
            "generator": generate_library_docs_url,
            "max_version": "boost_1_60_0",
            "alternate_slug": "functional/overloaded_function",
        }
    ],
    "graphparallel": [
        {
            "generator": generate_library_docs_url,
            "max_version": "boost_1_60_0",
            "min_version": "boost_1_40",
            "alternate_slug": "graph_parallel",
        }
    ],
    "identity-type": [
        {
            "generator": generate_library_docs_url_utility_v2,
            "max_version": "boost_1_60_0",
        }
    ],
    "in-place-factory-typed-in-place-factory": [
        {
            "generator": generate_library_docs_url_utility_v3,
            "max_version": "boost_1_60_0",
            "alternate_slug": "in_place_factories",
        }
    ],
    "interprocess": [
        {"generator": generate_library_docs_url_v4, "max_version": "boost_1_47_0"}
    ],
    "interval": [
        {"generator": generate_library_docs_url_numeric, "max_version": "boost_1_47_0"}
    ],
    "intrusive": [
        {"generator": generate_library_docs_url_v4, "max_version": "boost_1_47_0"}
    ],
    # Nothing before 1.63.0, so need to add that
    "io": [
        {"generator": generate_library_docs_url_v2, "min_version": "boost_1_73_0"},
        {
            "generator": generate_library_docs_url_v3,
            "min_version": "boost_1_64_0",
            "max_version": "boost_1_72_0",
        },
    ],
    # Not loading before 1.51.0
    "iterator": [
        {"generator": generate_library_docs_url_v3, "min_version": "boost_1_52_0"},
    ],
    "lexical-cast": [
        {
            "generator": generate_library_docs_url_v4,
            "max_version": "boost_1_60_0",
            "alternate_slug": "boost_lexical_cast",
        }
    ],
    "local-function": [
        {"generator": generate_library_docs_url, "max_version": "boost_1_60_0"}
    ],
    "math-common-factor": [
        {
            "generator": generate_library_docs_url_math_v1,
            "max_version": "boost_1_60_0",
            "alternate_slug": "gcd_lcm",
        }
    ],
    "math-octonion": [
        {
            "generator": generate_library_docs_url_math_v1,
            "max_version": "boost_1_60_0",
            "alternate_slug": "octonions",
        }
    ],
    "math-quaternion": [
        {
            "generator": generate_library_docs_url_math_v1,
            "max_version": "boost_1_60_0",
            "alternate_slug": "quaternions",
        }
    ],
    "mathspecial-functions": [
        {
            "generator": generate_library_docs_url_math_v1,
            "max_version": "boost_1_60_0",
            "alternate_slug": "special",
        }
    ],
    "member-function": [
        {
            "generator": generate_library_docs_url_bind_v1,
            "max_version": "boost_1_60_0",
            "min_version": "boost_1_59_0",
            "alternate_slug": "mem_fn",
        },
        {
            "generator": generate_library_docs_url_bind_v2,
            "max_version": "boost_1_57_0",
            "alternate_slug": "mem_fn",
        },
    ],
    "min-max": [
        {
            "generator": generate_library_docs_url_algorithm,
            "max_version": "boost_1_60_0",
            "alternate_slug": "minmax",
        }
    ],
    "multi-array": [
        {"generator": generate_library_docs_url_v3, "max_version": "boost_1_60_0"},
    ],
    "multi-index": [
        {"generator": generate_library_docs_url_v3, "max_version": "boost_1_60_0"},
    ],
    "numeric-conversion": [
        {
            "generator": generate_library_docs_url_numeric_2,
            "max_version": "boost_1_60_0",
            "alternate_slug": "conversion",
        }
    ],
    "program-options": [
        {"generator": generate_library_docs_url_v4, "max_version": "boost_1_60_0"}
    ],
    "result-of": [
        {
            "generator": generate_library_docs_url_utility_anchor,
            "max_version": "boost_1_60_0",
        }
    ],
    "scope-exit": [
        {"generator": generate_library_docs_url, "max_version": "boost_1_60_0"}
    ],
    "smart-ptr": [
        {
            "generator": generate_library_docs_url_double_nested_library_htm,
            "max_version": "boost_1_60_0",
        }
    ],
    "static-assert": [
        {
            "generator": generate_library_docs_url_double_nested_library_htm,
            "max_version": "boost_1_60_0",
        }
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
    # Still need to deal with the upload changes
    "string-view": [
        {
            "generator": generate_library_docs_url_string_view,
            "max_version": "boost_1_83_0",
        }
    ],
    "throwexception": [
        {
            "generator": generate_library_docs_url_throwexception,
            "max_version": "boost_1_60_0",
            "alternate_slug": "boost_throw_exception_hpp",
        }
    ],
    "type-erasure": [
        {
            "generator": generate_library_docs_url_v4,
            "max_version": "boost_1_60_0",
            "alternate_slug": "boost_typeerasure",
        }
    ],
    "type-index": [
        {
            "generator": generate_library_docs_url_v4,
            "max_version": "boost_1_60_0",
            "alternate_slug": "boost_typeindex",
        }
    ],
    # Not loading before 1.34.0
    "type-traits": [
        {"generator": generate_library_docs_url, "max_version": "boost_1_60_0"}
    ],
    # Missing before 1.60.0
    "winapi": [{"generator": generate_library_docs_url}],
    # Not loading the ones before 1.60.0
    "value-initialized": [
        {
            "generator": generate_library_docs_url_utility_v1,
            "max_version": "boost_1_60_0",
            "alternate_slug": "value_init",
        }
    ],
}


@app.task
def update_library_version_documentation_urls_all_versions():
    """Run the task to update all documentation URLs for all versions"""
    for version in Version.objects.all():
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
