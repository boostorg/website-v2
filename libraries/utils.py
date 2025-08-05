import random
import string
import re
from itertools import islice

import structlog
import tempfile
from datetime import datetime
from dateutil.relativedelta import relativedelta

from dateutil.parser import ParserError, parse
from django.utils.text import slugify

from libraries.constants import (
    DEFAULT_LIBRARIES_LANDING_VIEW,
    SELECTED_BOOST_VERSION_COOKIE_NAME,
    SELECTED_LIBRARY_VIEW_COOKIE_NAME,
    LATEST_RELEASE_URL_PATH_STR,
    LEGACY_LATEST_RELEASE_URL_PATH_STR,
    DEVELOP_RELEASE_URL_PATH_STR,
    MASTER_RELEASE_URL_PATH_STR,
)
from versions.models import Version

logger = structlog.get_logger()


def decode_content(content):
    """Decode bytes to string."""
    if isinstance(content, bytes):
        return content.decode("utf-8")
    return content


def generate_fake_email(val: str) -> str:
    """Slugify a string to make a fake email.

    Would not necessarily be unique -- this is a lazy way for us to avoid creating
    multiple new user records for one contributor who contributes to multiple libraries.
    """
    slug = slugify(val)
    local_email = slug.replace("-", "_")[:50]
    return f"{local_email}@example.com"


def generate_random_string(length=4):
    characters = string.ascii_letters
    random_string = "".join(random.choice(characters) for _ in range(length))
    return random_string


def version_within_range(
    version: str, min_version: str = None, max_version: str = None
):
    """Direct string comparison, assuming 'version', 'min_version', and 'max_version'
    follow the same format.

    Expects format `boost-1.84.0`
    """
    if min_version and version < min_version:
        return False
    if max_version and version > max_version:
        return False
    return True


def get_first_last_day_last_month():
    now = datetime.now()
    first_day_this_month = now.replace(day=1)
    last_day_last_month = first_day_this_month - relativedelta(days=1)
    first_day_last_month = last_day_last_month.replace(day=1)
    return first_day_last_month, last_day_last_month


def parse_date(date_str):
    """Parses a date string to a datetime. Does not return an error."""
    try:
        return parse(date_str)
    except ParserError:
        logger.info("parse_date_invalid_date", date_str=date_str)
        return None


def write_content_to_tempfile(content):
    """Accepts string or bytes content, writes it to a temporary file, and returns the
    file object."""
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        if isinstance(content, bytes):
            temp_file = open(temp_file.name, "wb")
        temp_file.write(content)
        temp_file.close()
    return temp_file


def get_version_from_url(request):
    return request.GET.get("version")


def get_version_from_cookie(request):
    return request.COOKIES.get(SELECTED_BOOST_VERSION_COOKIE_NAME)


def get_view_from_url(request):
    return request.resolver_match.kwargs.get("library_view_str")


def get_view_from_cookie(request):
    return request.COOKIES.get(SELECTED_LIBRARY_VIEW_COOKIE_NAME)


def set_view_in_cookie(response, view):
    allowed_views = {"grid", "list", "categorized"}
    if view not in allowed_views:
        return
    response.set_cookie(SELECTED_LIBRARY_VIEW_COOKIE_NAME, view)


def get_prioritized_version(request):
    """
    Version Priorities:
    1. URL parameter
    2. Cookie
    3. Default to latest version
    """
    url_version = get_version_from_url(request)
    cookie_version = get_version_from_cookie(request)
    default_version = None
    return url_version or cookie_version or default_version


def get_prioritized_library_view(request):
    """
    View Priorities:
    1. URL parameter
    2. Cookie
    3. Default to grid view
    """
    url_view = get_view_from_url(request)
    cookie_view = get_view_from_cookie(request)
    return url_view or cookie_view or DEFAULT_LIBRARIES_LANDING_VIEW


def get_category(request):
    return request.GET.get("category", "")


def determine_selected_boost_version(request_value, request):
    # use the versions in the request if they are available otherwise fall back to DB
    version_slug = request_value or get_version_from_cookie(request)
    version_args = {}
    if version_slug in (DEVELOP_RELEASE_URL_PATH_STR, MASTER_RELEASE_URL_PATH_STR):
        version_args = {f"allow_{version_slug}": True}

    valid_versions = getattr(request, "extra_context", {}).get(
        "versions", Version.objects.get_dropdown_versions(**version_args)
    )
    if version_slug in [v.slug for v in valid_versions] + [LATEST_RELEASE_URL_PATH_STR]:
        return version_slug
    logger.warning(f"Invalid version slug in cookies: {version_slug}")
    return None


def set_selected_boost_version(version_slug: str, response) -> None:
    """Update the selected version in the cookies."""
    versions_kwargs = {}
    if version_slug in [MASTER_RELEASE_URL_PATH_STR, DEVELOP_RELEASE_URL_PATH_STR]:
        versions_kwargs[f"allow_{version_slug}"] = True

    valid_versions = Version.objects.get_dropdown_versions(**versions_kwargs)
    if version_slug in [v.slug for v in valid_versions]:
        response.set_cookie(SELECTED_BOOST_VERSION_COOKIE_NAME, version_slug)
    elif version_slug == LATEST_RELEASE_URL_PATH_STR:
        response.delete_cookie(SELECTED_BOOST_VERSION_COOKIE_NAME)
    else:
        logger.warning(f"Attempted to set invalid version slug: {version_slug}")


def library_doc_latest_transform(url):
    p = re.compile(r"^(/doc/libs/)[0-9_]+(/\S+)$")
    if p.match(url):
        url = p.sub(rf"\1{LATEST_RELEASE_URL_PATH_STR}\2", url)
    return url


def get_documentation_url(library_version, latest):
    """Get the documentation URL for the current library."""

    def find_documentation_url(library_version):
        # If we know the library-version docs are missing, return the version docs
        if library_version.missing_docs:
            return library_version.version.documentation_url
        # If we have the library-version docs and they are valid, return those
        elif library_version.documentation_url:
            return library_version.documentation_url
        # If we wind up here, return the version docs
        else:
            return library_version.version.documentation_url

    # Get the URL for the version.
    url = find_documentation_url(library_version)
    # Remove the "boost_" prefix from the URL.
    url = url.replace("boost_", "")
    if latest:
        url = library_doc_latest_transform(url)

    return url


def batched(iterable, n, *, strict=False):
    # batched('ABCDEFG', 3) → ABC DEF G
    # In python 3.12, this function can be deleted in favor of itertools.batched
    if n < 1:
        raise ValueError("n must be at least one")
    iterator = iter(iterable)
    while batch := tuple(islice(iterator, n)):
        if strict and len(batch) != n:
            raise ValueError("batched(): incomplete batch")
        yield batch


def conditional_batched(iterable, n: int, condition: callable, *, strict=False):
    """
    Batch items that pass a condition together, return items that fail individually.

    Args:
        iterable: Items to process
        n: Batch size for items that pass the condition
        condition: Function that returns True if item should be batched
        strict: If True, raise error for incomplete final batch

    Yields:
        Tuples of batched items or single-item tuples for items that fail condition
    """
    if n < 1:
        raise ValueError("n must be at least one")

    batch = []

    for item in iterable:
        if condition(item):
            # item passes condition - add to batch
            batch.append(item)
            if len(batch) == n:
                # batch is full - yield it and start new batch
                yield tuple(batch)
                batch = []
        else:
            # item fails condition - yield any pending batch first, then item alone
            if batch:
                yield tuple(batch)
                batch = []
            yield (item,)

    # handle any remaining items in batch
    if strict and batch and len(batch) != n:
        raise ValueError("conditional_batched(): incomplete batch")
    if batch:
        yield tuple(batch)


def legacy_path_transform(content_path):
    if content_path and content_path.startswith(LEGACY_LATEST_RELEASE_URL_PATH_STR):
        content_path = re.sub(r"([a-zA-Z0-9\.]+)/(\S+)", r"latest/\2", content_path)
    return content_path


def parse_boostdep_artifact(content: str):
    """Parse and return a generator which yields libraries and their dependencies.

    - `content` is a string of the artifact content given by the dependency_report
        GH action.
    - Iterate through the file and yield a tuple of
        (library_version: LibraryVersion, dependencies: list[Library])
    - Some library keys in the output do not match the names in our database exactly,
        so transform names when necessary
    - The boost database may not contain every library version found in this file,
        if we find a definition of dependencies for a library version we are not
        tracking, ignore it and continue to the next line.
    - example content can be found in
        libraries/tests/fixtures.py -> github_action_boostdep_output_artifact

    """
    from libraries.models import Library, LibraryVersion

    libraries = {x.key: x for x in Library.objects.all()}
    # these libraries do not exist in the DB, ignore them.
    ignore_libraries = ["disjoint_sets", "tr1"]

    def fix_library_key(name):
        """Transforms library key in boostdep report to match our library keys"""
        if name == "logic":
            return "logic/tribool"
        return name.replace("~", "/")

    def parse_line(line: str):
        parts = line.split("->")
        if len(parts) == 2:
            library_key, dependencies_string = [x.strip() for x in parts]
            library_key = fix_library_key(library_key)
            dependency_names = [fix_library_key(x) for x in dependencies_string.split()]
            dependencies = [
                libraries[x] for x in dependency_names if x not in ignore_libraries
            ]
        else:
            library_key = fix_library_key(parts[0].strip())
            dependencies = []
        return library_key, dependencies

    library_versions = {}
    version_name = ""
    skipped_library_versions = 0
    for line in content.splitlines():
        # each section is headed with 'Dependencies for version boost-x.x.0'
        if line.startswith("Dependencies for version"):
            version_name = line.split()[-1]
            library_versions = {
                x.library.key: x
                for x in LibraryVersion.objects.filter(
                    version__name=version_name
                ).select_related("library")
            }
        else:
            library_key, dependencies = parse_line(line)
            if library_key in ignore_libraries:
                continue
            library_version = library_versions.get(library_key, None)
            if not library_version:
                skipped_library_versions += 1
                logger.info(
                    f"LibraryVersion with {library_key=} {version_name=} not found."
                )
                continue
            yield library_version, dependencies
    if skipped_library_versions:
        logger.info(
            "Some library versions were skipped during artifact parsing.",
            skipped_library_versions=skipped_library_versions,
        )
