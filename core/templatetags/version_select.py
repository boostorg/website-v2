from django import template
from django.template.loader import render_to_string

register = template.Library()


@register.simple_tag(takes_context=True)
def version_select(context):
    return render_to_string("partials/version_select.html", context.flatten())
