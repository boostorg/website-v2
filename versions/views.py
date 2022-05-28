from django.views.generic import ListView, DetailView

from versions.models import Version, VersionFile


class VersionList(ListView):
    """Web display of list of Versions"""

    model = Version
    queryset = Version.objects.active()
    template_name = "versions/list.html"


class VersionDetail(DetailView):
    """Web display of list of Versions"""

    model = Version
    queryset = Version.objects.active()
    template_name = "versions/detail.html"
