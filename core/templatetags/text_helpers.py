from django import template
from django.template.defaultfilters import stringfilter
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
        word = match.group(0)
        if len(word) > ln:
            start = word[: ln // 2]
            end = word[-((ln + 1) // 2) :]
            return f"{start}...{end}"
        return word

    pattern = re.compile(r"\b\w+\b")

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
