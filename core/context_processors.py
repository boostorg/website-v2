from dataclasses import dataclass
from enum import StrEnum

from django.conf import settings
from django.urls import reverse

from versions.models import Version


def current_version(request):
    """Custom context processor that adds the current release to the context"""
    return {"current_version": Version.objects.most_recent()}


class NavItem(StrEnum):
    LIBRARIES = "libraries"
    LEARN = "learn"
    NEWS = "news"
    COMMUNITY = "community"
    RELEASES = "releases"


_PATH_MAP = {
    "/doc/libs/": NavItem.LIBRARIES,  # special case - handle first
    "/doc/": NavItem.LEARN,
    "/docs/": NavItem.LEARN,
    "/boost-development/": NavItem.LEARN,
    "/news/": NavItem.NEWS,
    "/community/": NavItem.COMMUNITY,
    "/library/": NavItem.LIBRARIES,
    "/libraries/": NavItem.LIBRARIES,
    "/releases/": NavItem.RELEASES,
}


def _get_active_nav_item(request):
    """Determines the active nav item based on the request path."""
    for prefix, item in _PATH_MAP.items():
        if request.path.startswith(prefix):
            return item
    return "home"


def active_nav_item(request):
    """Custom context processor that adds the active nav item to the context"""
    return {"active_nav_item": _get_active_nav_item(request)}


@dataclass
class NavLink:
    """A single header navigation link."""

    label: str
    url: str
    nav_id: str = ""
    is_unread: bool = False


def header_context(request):
    """Context processor for header nav links."""
    nav_links = [
        NavLink(label="Libraries", url=reverse("libraries"), nav_id="libraries"),
        NavLink(label="Learn", url=reverse("docs"), nav_id="learn"),
        NavLink(label="Community", url=reverse("community"), nav_id="community"),
        NavLink(
            label="Posts", url=reverse("news"), nav_id="news", is_unread=True
        ),  # TODO: update is_unread based on actual unread state
        NavLink(
            label="Download", url=reverse("releases-most-recent"), nav_id="releases"
        ),
    ]
    return {
        "nav_links": nav_links,
        "releases_url": reverse("releases-most-recent"),
    }


def debug(request):
    """
    Adds settings.DEBUG to the context.
    """
    return {"DEBUG": settings.DEBUG}
