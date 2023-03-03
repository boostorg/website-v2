import re
import structlog

from dateutil.parser import ParserError, parse

from django.core.exceptions import ValidationError
from django.core.validators import validate_email

logger = structlog.get_logger()


def parse_date(date_str):
    """Parses a date string to a datetime. Does not return an error."""
    try:
        return parse(date_str)
    except ParserError:
        logger.info("parse_date_invalid_date", date_str=date_str)
        return None


def extract_email(val: str) -> str:
    """
    Finds an email address in a string, reformats it, and returns it.

    Assumes the email address is in this format:
    <firstlast -at- domain.com>
    """
    result = re.search("<.+>", val)
    if result:
        raw_email = result.group()
        email = (
            raw_email.replace("-at-", "@")
            .replace("<", "")
            .replace(">", "")
            .replace(" ", "")
        )
        try:
            validate_email(email)
        except ValidationError as e:
            # TODO: Output this to a list of some sort
            logger.info("Could not extract valid email", value=val)
            return
        return email
