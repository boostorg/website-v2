from urllib.parse import urlencode

import structlog
from django.urls import reverse

from libraries.constants import LATEST_RELEASE_URL_PATH_STR
from libraries.utils import determine_selected_boost_version
from versions.models import Version

logger = structlog.get_logger()


class VersionAlertMixin:
    """Mixin to selectively add a version alert to the context"""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_release = Version.objects.most_recent()
        url_name = self.request.resolver_match.url_name
        url_names_version_slug_override = {
            "library-detail": "version_slug",
            "library-detail-by-version": "version_slug",
        }
        version_slug_name = url_names_version_slug_override.get(url_name, "slug")
        version_slug = self.kwargs.get(
            version_slug_name,
            self.request.GET.get("version"),
        )
        selected_boost_version = determine_selected_boost_version(
            version_slug, self.request
        )
        if not selected_boost_version:
            selected_boost_version = LATEST_RELEASE_URL_PATH_STR
            version_slug = LATEST_RELEASE_URL_PATH_STR
        try:
            selected_version = Version.objects.get(slug=selected_boost_version)
        except Version.DoesNotExist:
            selected_version = current_release

        def generate_reverse(url_name):
            if url_name in {
                "libraries-mini",
                "libraries-by-category",
                "libraries-grid",
            }:
                url = reverse(url_name)
                params = {"version": LATEST_RELEASE_URL_PATH_STR}
                return f"{url}?{urlencode(params)}"
            elif url_name == "library-detail-by-version":
                library_slug = self.kwargs.get(
                    "slug"
                )  # only really accurately set on library detail page
                return reverse("library-detail", args=[library_slug])
            elif url_name == "release-detail":
                return reverse(url_name, args=[LATEST_RELEASE_URL_PATH_STR])

        # 'version_str' is representative of what the user has chosen, while 'version'
        # is the actual version instance that will be used in the template. We use the
        # value of LATEST_RELEASE_URL_PATH_STR as the default in order to normalize
        # behavior
        context["version"] = selected_version
        context["version_str"] = version_slug
        context["LATEST_RELEASE_URL_PATH_STR"] = LATEST_RELEASE_URL_PATH_STR
        context["current_release"] = current_release
        context["version_alert"] = context["version_str"] != LATEST_RELEASE_URL_PATH_STR
        context["version_alert_url"] = generate_reverse(url_name)
        return context
