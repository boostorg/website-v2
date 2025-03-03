from django import template

register = template.Library()


@register.filter(name="get_modulo_item")
def get_modulo_item_tag(list_obj, index):
    try:
        return list_obj[index % len(list_obj)]
    except (IndexError, TypeError):
        return ""
