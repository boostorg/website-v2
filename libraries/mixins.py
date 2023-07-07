import structlog

from versions.models import Version


logger = structlog.get_logger()


class VersionAlertMixin:
    """Mixin to selectively add a version alert to the context"""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get the version from the GET parameters or default to the latest
        version_slug = self.request.GET.get(
            "version", Version.objects.most_recent().slug
        )

        try:
            selected_version = Version.objects.get(slug=version_slug)
        except Version.DoesNotExist:
            selected_version = Version.objects.most_recent()

        # compare the selected version with the latest version
        latest_version = Version.objects.most_recent()
        context["latest_version"] = latest_version
        context["version"] = selected_version

        if selected_version != latest_version:
            context["version_alert"] = True
        else:
            context["version_alert"] = False

        return context
