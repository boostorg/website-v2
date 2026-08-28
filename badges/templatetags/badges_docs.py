"""Templatetags for the badges admin documentation page."""

from pathlib import Path

from django import template
from django.conf import settings
from django.utils.safestring import mark_safe

from core.markdown import process_md

register = template.Library()


@register.simple_tag
def render_badges_docs():
    """Render ``docs/badges-admin.md`` through the site's markdown pipeline.

    The file is the single source of truth for the Badges admin documentation:
    editing it changes the page without touching a template. The renderer is
    the same one the site uses for its markdown pages.
    """
    path = Path(settings.BASE_DIR) / "docs" / "badges-admin.md"
    _, rendered = process_md(path)
    return mark_safe(rendered)
