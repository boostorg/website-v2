from itertools import islice
import random
import string
import re

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
    valid_versions = Version.objects.version_dropdown_strict()
    version_slug = request_value or get_version_from_cookie(request)
    if version_slug in [v.slug for v in valid_versions] + [LATEST_RELEASE_URL_PATH_STR]:
        return version_slug
    else:
        logger.warning(f"Invalid version slug in cookies: {version_slug}")
        return None


def set_selected_boost_version(version_slug: str, response) -> None:
    """Update the selected version in the cookies."""
    valid_versions = Version.objects.version_dropdown_strict()
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


def legacy_path_transform(content_path):
    if content_path and content_path.startswith(LEGACY_LATEST_RELEASE_URL_PATH_STR):
        content_path = re.sub(r"([a-zA-Z0-9\.]+)/(\S+)", r"latest/\2", content_path)
    return content_path
