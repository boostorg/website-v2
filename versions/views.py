import structlog

from django.views.generic import DetailView
from django.views.generic.edit import FormMixin
from django.shortcuts import redirect

from libraries.forms import VersionSelectionForm
from versions.models import Version

logger = structlog.get_logger(__name__)


class VersionDetail(FormMixin, DetailView):
    """Web display of list of Versions"""

    form_class = VersionSelectionForm
    model = Version
    queryset = Version.objects.active()
    template_name = "versions/detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        context["versions"] = Version.objects.active().order_by("-release_date")
        current_release = Version.objects.most_recent()
        context["current_release"] = current_release
        obj = self.get_object()
        context["is_current_release"] = bool(current_release == obj)

        return context

    def post(self, request, *args, **kwargs):
        """User has submitted a form and will be redirected to the right record."""
        form = self.get_form()
        if form.is_valid():
            version = form.cleaned_data["version"]
            return redirect(
                "release-detail",
                slug=version.slug,
            )
        else:
            logger.info("version_detail_invalid_version")
        return super().get(request)


class VersionCurrentReleaseDetail(VersionDetail):
    """Web display of list of Versions"""

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        context["is_current_release"] = True
        return context

    def get_object(self):
        return Version.objects.most_recent()
