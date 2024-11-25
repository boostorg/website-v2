import structlog
from django.urls import reverse

from libraries.constants import LATEST_RELEASE_URL_PATH_STR
from versions.models import Version

logger = structlog.get_logger()


class VersionAlertMixin:
    """Mixin to selectively add a version alert to the context"""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        url_name = self.request.resolver_match.url_name
        if url_name in {"libraries", "releases-most-recent"}:
            return context
        current_version_kwargs = self.kwargs.copy()
        current_version_kwargs.update({"version_slug": LATEST_RELEASE_URL_PATH_STR})
        context["version_alert_url"] = reverse(url_name, kwargs=current_version_kwargs)
        context["version_alert"] = (
            self.kwargs.get("version_slug") != LATEST_RELEASE_URL_PATH_STR
        )
        return context


class BoostVersionMixin:
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # todo: replace get_current_library_version on LibraryDetail with this +
        #  prefetch_related
        context.update(
            {
                "version_str": self.kwargs.get("version_slug"),
                "LATEST_RELEASE_URL_PATH_STR": LATEST_RELEASE_URL_PATH_STR,
            }
        )
        if not context.get("current_version"):
            context["current_version"] = Version.objects.most_recent()

        if context["version_str"] == LATEST_RELEASE_URL_PATH_STR:
            context["selected_version"] = context["current_version"]
        elif context["version_str"]:
            context["selected_version"] = Version.objects.get(
                slug=context["version_str"]
            )

        return context
