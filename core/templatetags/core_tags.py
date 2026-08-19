import uuid
from django import template

from core.constants import (
    ACHIEVEMENTS_DIALOG_DESCRIPTION,
    ACHIEVEMENTS_DIALOG_ITEMS,
    BADGES_DIALOG_DESCRIPTION,
    BADGES_DIALOG_ITEMS,
)

register = template.Library()


@register.simple_tag
def generate_uuid():
    return uuid.uuid4()


@register.simple_tag
def achievements_dialog_content():
    """Default copy for the Achievements dialog, for use with ``as``."""
    return {
        "description": ACHIEVEMENTS_DIALOG_DESCRIPTION,
        "items": ACHIEVEMENTS_DIALOG_ITEMS,
    }


@register.simple_tag
def badges_dialog_content():
    """Default copy for the Badges dialog, for use with ``as``."""
    return {
        "description": BADGES_DIALOG_DESCRIPTION,
        "items": BADGES_DIALOG_ITEMS,
    }
