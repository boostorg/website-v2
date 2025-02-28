import random
from django import template

register = template.Library()


@register.simple_tag
def random_image_tag(image_list: str) -> str:
    if not image_list:
        return ""
    return random.choice(image_list.split(","))
