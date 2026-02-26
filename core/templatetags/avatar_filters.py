from django import template

register = template.Library()


@register.filter(is_safe=True)
def avatar_initials(value):
    """
    Return 1–2 letter initials from a name.
    """
    if not isinstance(value, str):
        return "U"

    name = value.strip()
    if not name:
        return "U"

    parts = name.split(None, 2)
    first = parts[0]

    if not first:
        return "U"

    first_initial = first[0].upper()

    if len(parts) > 1 and parts[1]:
        return first_initial + parts[1][0].upper()

    return first_initial
