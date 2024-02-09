from datetime import datetime
from dateutil.relativedelta import relativedelta
import structlog
import tempfile

from dateutil.parser import ParserError, parse
from django.utils.text import slugify


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


def generate_library_docs_url(boost_url_slug, library_slug):
    """Generate a documentation url with a specific format

    General use
    """
    return f"/doc/libs/{boost_url_slug}/libs/{library_slug}/doc/html/index.html"


def generate_library_docs_url_v2(boost_url_slug, library_slug):
    """ "Generate a documentation url with a specific format

    For use primarily with IO, versions 1.73.0 and up
    """
    new_boost_url_slug = boost_url_slug.replace("boost_", "")
    return f"/doc/libs/{new_boost_url_slug}/libs/{library_slug}/doc/html/{library_slug}.html"  # noqa


def generate_library_docs_url_v3(boost_url_slug, library_slug):
    """ "Generate a documentation url with a specific format

    For use primarily with IO, versions 1.64.0-1.72.
    """
    return f"/doc/libs/{boost_url_slug}/libs/{library_slug}/doc/index.html"


def generate_library_docs_url_v4(boost_url_slug, library_slug):
    """Generate a documentation url with a specific format

    First used for Any, versions 1.33.0 and older
    """
    return f"/doc/libs/{boost_url_slug}/doc/html/{library_slug}.html"


def generate_library_docs_url_utility_v1(boost_url_slug, library_slug):
    """Generate a documentation url with a specific format

    First used for Call Traits, versions 1.60.0 and below.
    """
    return f"/doc/libs/{boost_url_slug}/libs/utility/{library_slug}.htm"


def generate_library_docs_url_utility_v2(boost_url_slug, library_slug):
    """Generate a documentation url with a specific format

    First used for Identity Types, version 1.60.0 and below.
    """
    return f"/doc/libs/{boost_url_slug}/libs/utility/{library_slug}/doc/html/index.html"


def generate_library_docs_url_utility_v3(boost_url_slug, library_slug):
    """Generate a documentation url with a specific format

    Same as v1, but .html and not .htm

    First used for In Place Factories, version 1.60.0 and below.
    """
    return f"/doc/libs/{boost_url_slug}/libs/utility/{library_slug}.html"


def generate_library_docs_url_circular_buffer(boost_url_slug, library_slug):
    """Generate a documentation url with a specific format

    First used with Circular Buffer v. 1.54.0 and before"""
    return f"/doc/libs/{boost_url_slug}/libs/{library_slug}/doc/{library_slug}.html"


def generate_library_docs_url_core(boost_url_slug, library_slug):
    """Generate a documentation url with a specific format

    First used for Enable If, versions 1.60.0 and below.
    """
    return f"/doc/libs/{boost_url_slug}/libs/core/doc/html/core/{library_slug}.html"


def generate_library_docs_url_double_nested_library_html(boost_url_slug, library_slug):
    """Generate a documentation url with a specific format

    First used for Dynamic Bitset, versions 1.60.0 and below.
    """
    return f"/doc/libs/{boost_url_slug}/libs/{library_slug}/{library_slug}.html"


def generate_library_docs_url_double_nested_library_htm(boost_url_slug, library_slug):
    """Generate a documentation url with a specific format

    Ends in .htm, not .html

    First used for Dynamic Bitset, versions 1.60.0 and below.
    """
    return f"/doc/libs/{boost_url_slug}/libs/{library_slug}/{library_slug}.htm"


def generate_library_docs_url_numeric(boost_url_slug, library_slug):
    """Generate a documentation url with a specific format

    First used with Interval, versions 1.60.0 and below"""
    return (
        f"/doc/libs/{boost_url_slug}/libs/numeric/{library_slug}/doc/{library_slug}.htm"
    )


def generate_library_docs_url_string_ref(boost_url_slug, library_slug):
    """Generate a documentation URL for the string-ref library-versions"""
    return f"/doc/libs/{boost_url_slug}/libs/utility/doc/html/{library_slug}.html"


def generate_library_docs_url_string_view(boost_url_slug, library_slug):
    """Generate a documentation URL for the string-view library-versions"""
    return f"/doc/libs/{boost_url_slug}/libs/utility/doc/html/utility/utilities/{library_slug}.html"  # noqa


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
