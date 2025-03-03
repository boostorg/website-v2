from django import template

register = template.Library()


@register.filter(name="split")
def split_tag(value, key):
    return value.split(key)
