import re

from django.core.exceptions import ValidationError


def validate_version_name_format(value: str) -> None:
    """
    Validate that the version name follows the format 'boost-X.Y.Zw' where X, Y, and Z
     are integers and w is freeform.
    """
    if value in ["master", "develop"]:
        return
    if not re.match(r"^boost-[0-9]+\.[0-9]+\.[0-9]+[.\-a-zA-Z0-9]*$", value):
        raise ValidationError(
            f"Invalid version name format: '{value}'. "
            "Expected format is that it begins with 'boost-X.Y.Zw' where X, Y, and Z "
            "are integers and w is free form."
        )
