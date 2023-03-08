import random
import re
import string

from django.utils.text import slugify


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
    """ Slugifies a string to make a fake email """
    slug = slugify(val)
    letters = string.ascii_lowercase
    suffix = ''.join(random.choice(letters) for i in range(8))
    local_email = slug.replace("-", "_")[:50]
    return f"{local_email}_{suffix}@example.com"

