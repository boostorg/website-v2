from django import template
from django.template.loader import render_to_string

register = template.Library()


@register.simple_tag()
def avatar(
    name,
    image_url,
    href,
    is_show_name=False,
    alt=None,
    title=None,
    image_size=None,
    icon_size=None,
):
    context = {
        "av_name": name,
        "av_href": href,
        "av_image_url": image_url,
        "av_show_name": is_show_name,
        "av_size": image_size,
        "av_icon_size": icon_size,
        "av_title": title,
        "av_alt": alt,
    }
    return render_to_string("partials/avatar.html", context)
