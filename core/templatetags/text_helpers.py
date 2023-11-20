from django import template
from django.template.defaultfilters import stringfilter

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
def url_target_blank(value, arg):
    """
    Use after urlize to add target="_blank" and add classes.
    """
    return value.replace("<a ", '<a target="_blank" class="%s" ') % (arg)
