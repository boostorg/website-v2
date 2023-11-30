from versions.models import Version


def current_release(request):
    """Custom context processor that adds the current release to the context"""
    current_release = Version.objects.most_recent()
    return {"current_release": current_release}
