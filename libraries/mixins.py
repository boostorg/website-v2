import structlog
from django.shortcuts import get_object_or_404
from django.urls import reverse

from libraries.constants import (
    LATEST_RELEASE_URL_PATH_STR,
    MASTER_RELEASE_URL_PATH_STR,
    DEVELOP_RELEASE_URL_PATH_STR,
)
from libraries.models import Library
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
    def dispatch(self, request, *args, **kwargs):
        self.set_extra_context(request)
        return super().dispatch(request, *args, **kwargs)

    def set_extra_context(self, request):
        if not self.extra_context:
            self.extra_context = {}
        if not self.extra_context.get("current_version"):
            self.extra_context["current_version"] = Version.objects.most_recent()
        self.extra_context.update(
            {
                "version_str": self.kwargs.get("version_slug"),
                "LATEST_RELEASE_URL_PATH_STR": LATEST_RELEASE_URL_PATH_STR,
            }
        )
        if self.extra_context["version_str"] == LATEST_RELEASE_URL_PATH_STR:
            self.extra_context["selected_version"] = self.extra_context[
                "current_version"
            ]
        elif self.extra_context["version_str"]:
            self.extra_context["selected_version"] = get_object_or_404(
                Version, slug=self.extra_context["version_str"]
            )
        version_path_kwargs = {}
        # Only when the user uses master or develop do those versions to appear
        if self.extra_context["version_str"] in [
            MASTER_RELEASE_URL_PATH_STR,
            DEVELOP_RELEASE_URL_PATH_STR,
        ]:
            version_path_kwargs[f"allow_{self.extra_context['version_str']}"] = True
        if self.request.resolver_match.view_name == "library-detail":
            version_path_kwargs["flag_versions_without_library"] = get_object_or_404(
                Library, slug=self.kwargs.get("library_slug")
            )
        self.extra_context["versions"] = Version.objects.get_dropdown_versions(
            **version_path_kwargs
        )
        # here we hack extra_context into the request so we can access for cookie checks
        request.extra_context = self.extra_context
