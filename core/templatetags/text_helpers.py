import json
from urllib.parse import urlparse, urlunparse

from django import template
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe
import re

register = template.Library()


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


# Escapes <, >, and & so that JSON embedded in a <script> tag cannot break out of
# it via sequences like </script> or <!-- regardless of string values in the data.
_JSON_SCRIPT_ESCAPES = {ord(">"): "\\u003E", ord("<"): "\\u003C", ord("&"): "\\u0026"}


@register.filter(is_safe=True)
def to_json(value):
    """Serialize value to a JSON string safe for embedding in <script> tags.

    A list of 2-tuples (e.g. from TextChoices.choices) is converted to
    [{"value": ..., "label": ...}, ...] before serializing, matching the
    shape expected by V3 form component Alpine.js code.
    """
    if value and isinstance(value[0], (list, tuple)):
        value = [{"value": v, "label": lbl} for v, lbl in value]
    return mark_safe(json.dumps(value).translate(_JSON_SCRIPT_ESCAPES))


@register.filter
def strip_query_string(url):
    """Remove query string from URL while preserving the path and other components."""
    if not url:
        return url
    parsed = urlparse(url)
    clean = parsed._replace(query="", fragment="")
    return urlunparse(clean)
