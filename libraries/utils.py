import re
import structlog

from dateutil.parser import ParserError, parse

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils.text import slugify

logger = structlog.get_logger()

User = get_user_model()


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
            logger.info("Could not extract valid email", value=val)
            return
        return email


def extract_names(name_str: str) -> list:
    """
    Returns a ,list of first, last names for the val argument.

    NOTE: This is an overly simplistic solution to importing names.
    Names that don't conform neatly to "First Last" formats will need
    to be cleaned up manually.

    Expects something similar to these formats:
    - "Tester Testerston <t_testerson -at- domain.com>"
    - "Tester de Testerson"
    """
    # Strip the email, if present
    email = re.search("<.+>", name_str)
    if email:
        name_str = name_str.replace(email.group(), "")

    return name_str.strip().rsplit(" ", 1)


def generate_email(val: str) -> str:
    """Takes a string and generates a placeholder email based on it"""
    slug = slugify(val)
    local_email = slug.replace("-", "_")[:64]
    return f"{local_email}@example.com"


def parse_date(date_str):
    """Parses a date string to a datetime. Does not return an error."""
    try:
        return parse(date_str)
    except ParserError:
        logger.info("parse_date_invalid_date", date_str=date_str)
        return None
