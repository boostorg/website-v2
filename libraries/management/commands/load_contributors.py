import re


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
