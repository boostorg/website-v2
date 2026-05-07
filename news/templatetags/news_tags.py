import re

from django import template
from django.template.defaultfilters import urlize
from django.utils.safestring import mark_safe

register = template.Library()

_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n+")
_LIST_MARKER = re.compile(r"^(?:[*\-+]\s|\d+[.)]\s)")
_SHORT_LINE_THRESHOLD = 60


def _should_preserve_breaks(lines):
    """Decide whether a paragraph's single newlines should render as <br>.

    Lists (bullet, dash, plus, or numbered) and short-line blocks
    (sign-offs like "Thank you,\nName") read as author-formatted
    layout; collapsing them to spaces destroys their meaning. Hard-
    wrapped prose has internal lines near 80 chars, so checking
    "any non-final line under 60 chars" identifies the former.
    """
    if any(_LIST_MARKER.match(line) for line in lines):
        return True
    return any(len(line) < _SHORT_LINE_THRESHOLD for line in lines[:-1])


@register.filter
def text_paragraphs(value):
    """Render hard-wrapped plain text as autolinked paragraphs.

    Blank lines become paragraph breaks. Within a paragraph, single
    newlines collapse to spaces so hard-wrapped (~80 char) source
    flows to container width, unless the paragraph looks author-
    formatted (list items or short-line sign-off), in which case
    the breaks are preserved as <br>.
    """
    if not value:
        return ""
    paragraphs = []
    for chunk in _PARAGRAPH_SPLIT.split(str(value)):
        lines = [line.strip() for line in chunk.splitlines() if line.strip()]
        if not lines:
            continue
        if _should_preserve_breaks(lines):
            joined = "<br>".join(urlize(line, autoescape=True) for line in lines)
        else:
            joined = urlize(" ".join(lines), autoescape=True)
        paragraphs.append(f"<p>{joined}</p>")
    return mark_safe("\n".join(paragraphs))


@register.simple_tag(takes_context=True)
def can_edit(context, news_item, *args, **kwargs):
    request = context.get("request")
    return news_item.can_edit(request.user)
