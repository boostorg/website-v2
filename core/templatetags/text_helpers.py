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
