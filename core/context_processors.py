from django.conf import settings

from versions.models import Version


def current_version(request):
    """Custom context processor that adds the current release to the context"""
    return {"current_version": Version.objects.most_recent()}


def active_nav_item(request):
    """Custom context processor that adds the active nav item to the context"""
    path = request.path
    default_nav_item = "home"
    path_map = {
        "/news/": "news",
        "/doc/": "learn",
        "/docs/": "learn",
        "/community/": "community",
        "/library/": "libraries",
        "/libraries/": "libraries",
        "/releases/": "releases",
    }
    for prefix, item in path_map.items():
        if path.startswith(prefix):
            return {"active_nav_item": item}
    return {"active_nav_item": default_nav_item}


def debug(request):
    """
    Adds settings.DEBUG to the context.
    """
    return {"DEBUG": settings.DEBUG}
