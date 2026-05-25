import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


_BACKTICK_RE = re.compile(r"`([^`]+)`")
_BOLD_RE = re.compile(r"\*\*([^*]+?)\*\*")


@register.filter
def inline_markdown(value):
    """Render inline-code (`...`) and bold (**...**) markdown spans as HTML.

    Scoped to what `WHATS_NEW_SYSTEM_PROMPT` permits in description bullets:
    code identifiers in single backticks and double-asterisk bold. Everything
    else in the input is HTML-escaped.
    """
    if not value:
        return ""
    rendered = escape(value)
    rendered = _BOLD_RE.sub(r"<strong>\1</strong>", rendered)
    rendered = _BACKTICK_RE.sub(r"<code>\1</code>", rendered)
    return mark_safe(rendered)
