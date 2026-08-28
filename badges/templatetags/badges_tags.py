"""Template access to the recognition catalogue.

The Achievements and Badges dialogs are self-contained includes: a caller drops
one on a page without wiring up context for it. Reading the catalogue through a
tag is what lets them stay that way.

Each tag takes the caller's own rows and falls back to the catalogue only when
there are none, so a caller that supplies rows pays no query.
"""

from django import template

from badges import display

register = template.Library()


@register.simple_tag
def achievements_dialog_content(items=None):
    """Content for the Achievements dialog, for use with ``as``."""
    return {
        "description": display.ACHIEVEMENTS_DIALOG_DESCRIPTION,
        "items": items or display.achievement_dialog_rows(),
    }


@register.simple_tag
def badges_dialog_content(items=None):
    """Content for the Badges dialog, for use with ``as``."""
    return {
        "description": display.BADGES_DIALOG_DESCRIPTION,
        "items": items or display.badge_dialog_rows(),
    }
