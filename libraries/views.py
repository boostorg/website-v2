from django.views.generic import ListView, DetailView

from .models import Library, Category


class CategoryMixin:
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = Category.objects.all().order_by("name")
        return context


class LibraryList(CategoryMixin, ListView):
    """List all of our libraries by name"""

    paginate_by = 25
    queryset = Library.objects.prefetch_related("categories").all().order_by("name")
    template_name = "libraries/list.html"


class LibraryByLetter(CategoryMixin, ListView):
    """List all of our libraries that begin with a certain letter"""

    paginate_by = 25
    template_name = "libraries/list.html"

    def get_queryset(self):
        letter = self.kwargs.get("letter")

        return (
            Library.objects.prefetch_related("categories")
            .filter(name__startswith=letter.lower())
            .order_by("name")
        )


class LibraryByCategory(CategoryMixin, ListView):
    """List all of our libraries in a certain category"""

    paginate_by = 25
    template_name = "libraries/list.html"

    def get_queryset(self):
        category = self.kwargs.get("category")

        return (
            Library.objects.prefetch_related("categories")
            .filter(categories__slug=category)
            .order_by("name")
        )


class LibraryDetail(CategoryMixin, DetailView):
    """Display a single Library in insolation"""

    model = Library
    template_name = "libraries/detail.html"
