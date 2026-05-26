import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


# Single pass with backtick listed first so a code span wins over bold at the
# same position — e.g. `a**b**c` stays a code span, the inner ** is not bolded.
_INLINE_RE = re.compile(r"`([^`]+)`|\*\*([^*]+?)\*\*")


def _replace_span(match):
    if match.group(1) is not None:
        return f"<code>{match.group(1)}</code>"
    return f"<strong>{match.group(2)}</strong>"


@register.filter
def inline_markdown(value):
    """Render inline-code (`...`) and bold (**...**) markdown spans as HTML.

    Scoped to what `WHATS_NEW_SYSTEM_PROMPT` permits in description bullets:
    code identifiers in single backticks and double-asterisk bold. Everything
    else in the input is HTML-escaped.
    """
    if not value:
        return ""
    return mark_safe(_INLINE_RE.sub(_replace_span, escape(value)))
