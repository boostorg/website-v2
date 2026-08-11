from django import template
from django.urls import reverse

register = template.Library()


@register.simple_tag()
def branch_url_tag(view: str, branch: str, kwargs: dict):
    return reverse(view, kwargs={**kwargs, "version_slug": branch})
