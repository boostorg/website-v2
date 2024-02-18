#
# Copyright (c) 2024 The C++ Alliance, Inc. (https://cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/boostorg/website-v2
#
import structlog

from versions.models import Version


logger = structlog.get_logger()


class VersionAlertMixin:
    """Mixin to selectively add a version alert to the context"""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        latest_version = Version.objects.most_recent()
        version_slug = self.request.GET.get(
            "version", latest_version.slug if latest_version else None
        )

        selected_version = None
        if version_slug:
            try:
                selected_version = Version.objects.get(slug=version_slug)
            except Version.DoesNotExist:
                selected_version = latest_version

        context["latest_version"] = latest_version
        context["version"] = selected_version

        if selected_version and latest_version:
            context["version_alert"] = selected_version != latest_version
        else:
            context["version_alert"] = False

        return context
