import re

from django import template
from django.template.defaultfilters import urlize
from django.utils.safestring import mark_safe

register = template.Library()

_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n+")


@register.filter
def text_paragraphs(value):
    """Render hard-wrapped plain text as autolinked paragraphs.

    Blank lines become paragraph breaks; single newlines inside a
    paragraph collapse to spaces so source hard-wrapped at ~80 chars
    flows naturally to the container width.
    """
    if not value:
        return ""
    paragraphs = []
    for chunk in _PARAGRAPH_SPLIT.split(str(value)):
        text = " ".join(line.strip() for line in chunk.splitlines() if line.strip())
        if text:
            paragraphs.append(f"<p>{urlize(text, autoescape=True)}</p>")
    return mark_safe("\n".join(paragraphs))


@register.simple_tag(takes_context=True)
def can_edit(context, news_item, *args, **kwargs):
    request = context.get("request")
    return news_item.can_edit(request.user)
