from django import template

register = template.Library()


@register.filter
def boost_version(slug):
    return slug.replace("boost-", "").replace("-", ".")
