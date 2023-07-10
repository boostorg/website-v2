from django.views.generic import DetailView

from versions.models import Version


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
