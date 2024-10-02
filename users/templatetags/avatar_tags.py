from django import template
from django.template.loader import render_to_string

register = template.Library()


@register.simple_tag()
def base_avatar(
    name,
    image_url,
    href,
    is_link=True,
    is_show_name=False,
    alt=None,
    title=None,
    image_size=None,
    icon_size=None,
    is_new=False,
):
    context = {
        "av_name": name,
        "av_href": href,
        "av_is_link": is_link,
        "av_image_url": image_url,
        "av_show_name": is_show_name,
        "av_size": image_size,
        "av_icon_size": icon_size,
        "av_title": title,
        "av_alt": alt,
        "av_is_new": is_new,
    }
    return render_to_string("partials/avatar.html", context)


@register.simple_tag()
def avatar(
    user=None,
    commitauthor=None,
    is_link=True,
    is_show_name=False,
    alt=None,
    title=None,
    image_size=None,
    icon_size=None,
    is_new=False,
):
    kwargs = {
        "is_link": is_link,
        "is_show_name": is_show_name,
        "alt": alt,
        "title": title,
        "image_size": image_size,
        "icon_size": icon_size,
        "is_new": is_new,
    }
    if user and commitauthor:
        image_url = user.get_thumbnail_url() or commitauthor.avatar_url
        href = user.github_profile_url or commitauthor.github_profile_url
        return base_avatar(
            user.get_full_name(),
            image_url,
            href,
            **kwargs,
        )
    elif user:
        return base_avatar(
            user.get_full_name(),
            user.get_thumbnail_url(),
            user.github_profile_url,
            **kwargs,
        )
    elif commitauthor:
        if isinstance(commitauthor, dict):
            name = commitauthor["name"]
            avatar_url = commitauthor["avatar_url"]
            github_profile_url = commitauthor["github_profile_url"]
        else:
            name = commitauthor.name
            avatar_url = commitauthor.avatar_url
            github_profile_url = commitauthor.github_profile_url
        return base_avatar(
            name,
            avatar_url,
            github_profile_url,
            **kwargs,
        )
    raise ValueError("Must provide user or commitauthor.")
