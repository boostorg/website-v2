import structlog

from dateutil.parser import ParserError, parse
from django.utils.text import slugify


logger = structlog.get_logger()


def generate_fake_email(val: str) -> str:
    """
    Slugifies a string to make a fake email. Would not necessarily be unique -- this is
    a lazy way for us to avoid creating multiple new user records for one contributor who
    contributes to multiple libraries.
    """
    slug = slugify(val)
    local_email = slug.replace("-", "_")[:50]
    return f"{local_email}@example.com"


def parse_date(date_str):
    """Parses a date string to a datetime. Does not return an error."""
    try:
        return parse(date_str)
    except ParserError:
        logger.info("parse_date_invalid_date", date_str=date_str)
        return None
