import random
import re
import string
import structlog

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils.text import slugify

logger = structlog.get_logger()


def extract_email(val: str) -> str:
    """
    Finds an email address in a string, reformats it, and returns it.
    Assumes the email address is in this format:
    <firstlast -at- domain.com>

    Does not raise errors.
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
            logger.info("Could not extract valid email", value=val, exc_msg=str(e))
            return
        return email


def extract_names(val: str) -> list:
    """
    Returns a list of first, last names for the val argument.

    NOTE: This is an overly simplistic solution to importing names.
    Names that don't conform neatly to "First Last" formats will need
    to be cleaned up manually.
    """
    # Strip the email, if present
    email = re.search("<.+>", val)
    if email:
        val = val.replace(email.group(), "")

    return val.strip().rsplit(" ", 1)


def generate_fake_email(val: str) -> str:
    """Slugifies a string to make a fake email"""
    slug = slugify(val)
    letters = string.ascii_lowercase
    suffix = "".join(random.choice(letters) for i in range(8))
    local_email = slug.replace("-", "_")[:50]
    return f"{local_email}_{suffix}@example.com"


def get_contributor_data(contributor: str) -> dict:
    """Takes an author/maintainer string and returns a dict with their data"""
    data = {}
    data["meta"] = contributor
    data["valid_email"] = False

    email = extract_email(contributor)
    if bool(email):
        data["email"] = email
        data["valid_email"] = True
    else:

        data["email"] = generate_fake_email(contributor)

    data["first_name"], data["last_name"] = extract_names(contributor)

    return data
