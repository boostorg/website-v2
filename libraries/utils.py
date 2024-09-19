import random
import string
import structlog
import tempfile
from datetime import datetime
from dateutil.relativedelta import relativedelta
from urllib.parse import urlencode

from dateutil.parser import ParserError, parse
from django.utils.text import slugify
from django.urls import reverse
from django.shortcuts import redirect

from libraries.constants import (
    DEFAULT_LIBRARIES_LANDING_VIEW,
    SELECTED_BOOST_VERSION_COOKIE_NAME,
    SELECTED_LIBRARY_VIEW_COOKIE_NAME,
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


def redirect_to_view_with_params(view_name, params, query_params):
    """Redirect to a view with parameters and query parameters."""
    base_url = reverse(view_name, kwargs=params)
    query_string = urlencode(query_params)
    url = base_url
    if query_string:
        url = "{}?{}".format(base_url, query_string)
    return redirect(url)


def get_version_from_url(request):
    return request.GET.get("version")


def get_version_from_cookie(request):
    return request.COOKIES.get(SELECTED_BOOST_VERSION_COOKIE_NAME)


def get_view_from_url(request):
    return request.GET.get("view")


def get_view_from_cookie(request):
    return request.COOKIES.get(SELECTED_LIBRARY_VIEW_COOKIE_NAME)


def set_view_in_cookie(response, view):
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


def build_view_query_params_from_request(request):
    query_params = {}
    version = get_prioritized_version(request)
    category = get_category(request)
    if version and version != "latest":
        query_params["version"] = version
    if category:
        query_params["category"] = category
    return query_params


def get_category(request):
    return request.GET.get("category", "")


def build_route_name_for_view(view):
    return f"libraries-{view}"


def determine_view_from_library_request(request):
    split_path_info = request.path_info.split("/")
    return None if split_path_info[-2] == "libraries" else split_path_info[-2]


def determine_selected_boost_version(request_value, request):
    valid_versions = Version.objects.version_dropdown_strict()
    version_slug = get_version_from_cookie(request) or request_value
    if version_slug in [v.slug for v in valid_versions]:
        return version_slug
    else:
        logger.warning(f"Invalid version slug in cookies: {version_slug}")
        return None


def set_selected_boost_version(version_slug: str, response) -> None:
    """Update the selected version in the cookies."""
    valid_versions = Version.objects.version_dropdown_strict()
    if version_slug in [v.slug for v in valid_versions]:
        response.set_cookie(SELECTED_BOOST_VERSION_COOKIE_NAME, version_slug)
    elif version_slug == "latest":
        response.delete_cookie(SELECTED_BOOST_VERSION_COOKIE_NAME)
    else:
        logger.warning(f"Attempted to set invalid version slug: {version_slug}")
