from django.views.generic import ListView, DetailView

from versions.models import Version


class VersionList(ListView):
    """Web display of list of Versions"""

    model = Version
    queryset = Version.objects.active().order_by("-release_date")
    template_name = "versions/list.html"

    def get_context_data(self):
        context = super().get_context_data()
        queryset = self.get_queryset()
        current_version = queryset.order_by("-release_date").first()
        context["current_version"] = current_version
        context["version_list"] = queryset.exclude(pk=current_version.pk)
        return context


class VersionDetail(DetailView):
    """Web display of list of Versions"""

    model = Version
    queryset = Version.objects.active()
    template_name = "versions/detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        current_version = Version.objects.most_recent()
        obj = self.get_object()
        context["current_version"] = bool(current_version == obj)
        return context
