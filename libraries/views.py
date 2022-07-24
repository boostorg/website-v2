from django.views.generic import ListView

from .models import Library


class LibraryList(ListView):
    """List all of our libraries by name"""

    paginate_by = 25
    queryset = Library.objects.prefetch_related("categories").all().order_by("name")
    template_name = "libraries/list.html"
