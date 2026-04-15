import uuid
from django import template

register = template.Library()


@register.simple_tag
def generate_uuid():
    return uuid.uuid4()
