from django.conf import settings

from versions.models import Version


def current_version(request):
    """Custom context processor that adds the current release to the context"""
    return {"current_version": Version.objects.most_recent()}


def debug(request):
    """
    Adds settings.DEBUG to the context.
    """
    return {"DEBUG": settings.DEBUG}
