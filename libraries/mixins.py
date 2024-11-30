from functools import partial

import structlog
from django.shortcuts import get_object_or_404
from django.urls import reverse

from libraries.constants import LATEST_RELEASE_URL_PATH_STR
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

        version_path_kwargs = {
            "release-detail": {},
            "libraries-list": {
                "filter_out_has_no_libraries": True,
                "force_version_inclusion": self.extra_context["current_version"],
            },
            "library-detail": {
                "flag_versions_without_library": partial(
                    get_object_or_404, Library, slug=self.kwargs.get("library_slug")
                )
            },
        }.get(self.request.resolver_match.view_name, {})
        # we need this step to process any partials
        processed_version_path_kwargs = {
            key: (value() if callable(value) else value)
            for key, value in version_path_kwargs.items()
        }

        self.extra_context["versions"] = Version.objects.get_dropdown_versions(
            **processed_version_path_kwargs
        )
        # here we hack extra_context into the request so we can access for cookie checks
        request.extra_context = self.extra_context
        return super().dispatch(request, *args, **kwargs)
