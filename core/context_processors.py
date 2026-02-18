from enum import StrEnum

from django.conf import settings
from waffle import flag_is_active

from versions.models import Version


def v3_enabled(request):
    """Expose v3 feature flag so templates can add html class for v3 typography/scope."""
    return {"v3_enabled": flag_is_active(request, "v3")}


def current_version(request):
    """Custom context processor that adds the current release to the context"""
    return {"current_version": Version.objects.most_recent()}


class NavItem(StrEnum):
    LIBRARIES = "libraries"
    LEARN = "learn"
    NEWS = "news"
    COMMUNITY = "community"
    RELEASES = "releases"


def active_nav_item(request):
    """Custom context processor that adds the active nav item to the context"""
    default_nav_item = "home"
    path_map = {
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
    for prefix, item in path_map.items():
        if request.path.startswith(prefix):
            return {"active_nav_item": item}
    return {"active_nav_item": default_nav_item}


def debug(request):
    """
    Adds settings.DEBUG to the context.
    """
    return {"DEBUG": settings.DEBUG}
