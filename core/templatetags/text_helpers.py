from urllib.parse import urlparse, urlunparse

import bleach
from django import template
from django.template.defaultfilters import stringfilter
import re

register = template.Library()

# Allowlist for WYSIWYG entry content (TipTap output): reduces XSS when rendering with safe.
SANITIZE_HTML_TAGS = [
    "p",
    "br",
    "strong",
    "em",
    "u",
    "b",
    "i",
    "ul",
    "ol",
    "li",
    "a",
    "code",
    "pre",
    "span",
]
SANITIZE_HTML_ATTRS = {
    "a": ["href", "target", "rel", "title"],
    "span": ["class"],
    "code": ["class"],
    "pre": ["class"],
}
SANITIZE_HTML_PROTOCOLS = ["http", "https", "mailto"]


@register.filter(is_safe=True)
@stringfilter
def truncate_middle(value, arg):
    try:
        ln = int(arg)
    except ValueError:
        return value
    if len(value) <= ln:
        return value
    else:
        return f"{value[:ln//2]}....{value[-((ln+1)//2):]}"


@register.filter(is_safe=True)
@stringfilter
def multi_truncate_middle(value, arg):
    def replace_match(match):
        word_or_link = match.group(0)

        link_inner_match = re.search(r"<a\b[^>]*>(.*?)<\/a>", word_or_link)

        if link_inner_match:
            word = re.sub(r"https?://", "", link_inner_match.group(1))

        else:
            word = word_or_link

        if link_inner_match:
            if len(word) > ln + 10:
                start = word[: ((ln + 10) // 2)]
                end = word[-(((ln + 10) + 1) // 2) :]
                truncated_word = f"{start}....{end}"
                return re.sub(
                    r"(<a\b[^>]*>)(.*?)(<\/a>)",
                    r"\1" + truncated_word + r"\3",
                    word_or_link,
                )
        elif len(word) > ln:
            start = word[: (ln // 2)]
            end = word[-((ln + 1) // 2) :]
            truncated_word = f"{start}....{end}"
            return truncated_word
        return word_or_link

    pattern = re.compile(
        r"\b(\w{" + str(arg) + r",})\b|<a\b[^>]*>((.|\n|\r|(\n\r))*?)<\/a>"
    )

    try:
        ln = int(arg)
    except ValueError:
        return value
    if len(value) <= ln:
        return value
    else:
        result = pattern.sub(replace_match, value)
        return result


@register.filter(is_safe=True)
@stringfilter
def url_target_blank(value, arg):
    """
    Use after urlize to add target="_blank" and add classes.
    """
    return value.replace("<a ", f'<a target="_blank" class="{arg}" ')


@register.filter(is_safe=True)
def sanitize_html_allowlist(value):
    """
    Sanitize HTML with an allowlist of tags and attributes (bleach).
    Use for WYSIWYG entry content before rendering to reduce XSS risk.
    """
    if not value or not isinstance(value, str):
        return value
    return bleach.clean(
        value,
        tags=SANITIZE_HTML_TAGS,
        attributes=SANITIZE_HTML_ATTRS,
        protocols=SANITIZE_HTML_PROTOCOLS,
        strip=False,
    )


@register.filter
def looks_like_html(value):
    """Return True if the string looks like HTML (e.g. from WYSIWYG), for conditional safe rendering."""
    if not value or not isinstance(value, str):
        return False
    stripped = value.strip()
    return stripped.startswith("<") and ">" in stripped


@register.filter
def strip_query_string(url):
    """Remove query string from URL while preserving the path and other components."""
    if not url:
        return url
    parsed = urlparse(url)
    clean = parsed._replace(query="", fragment="")
    return urlunparse(clean)
