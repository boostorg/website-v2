import structlog

from django.http import Http404
from django.shortcuts import redirect
from django.views.generic import DetailView, ListView
from django.views.generic.edit import FormMixin

from versions.models import Version
from .forms import LibraryForm
from .models import Category, Issue, Library, LibraryVersion, PullRequest

logger = structlog.get_logger()


class CategoryMixin:
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = Category.objects.all().order_by("name")
        return context


class LibraryList(CategoryMixin, FormMixin, ListView):
    """List all of our libraries by name"""

    form_class = LibraryForm
    paginate_by = 25
    queryset = (
        Library.objects.prefetch_related("authors", "categories").all().order_by("name")
    )
    template_name = "libraries/list.html"

    def post(self, request):
        """User has submitted a form and will be redirected to the right results"""
        form = self.get_form()
        if form.is_valid():
            category = form.cleaned_data["categories"][0]
            return redirect("libraries-by-category", category=category.slug)
        else:
            logger.info("library_list_invalid_category")
        return super().get(request)


class LibraryListByVersion(CategoryMixin, FormMixin, ListView):
    """List all of our libraries for a specific Boost version by name"""

    form_class = LibraryForm
    paginate_by = 25
    queryset = (
        Library.objects.prefetch_related("authors", "categories").all().order_by("name")
    )
    template_name = "libraries/list.html"

    def get_queryset(self):
        version_slug = self.kwargs.get("slug")
        return (
            super().get_queryset().filter(library_version__version__slug=version_slug)
        )

    def post(self, request):
        """User has submitted a form and will be redirected to the right results"""
        form = self.get_form()
        if form.is_valid():
            category = form.cleaned_data["categories"][0]
            return redirect("libraries-by-category", category=category.slug)
        else:
            logger.info("library_list_invalid_category")
        return super().get(request)


class LibraryDetailByVersion(CategoryMixin, DetailView):
    """Display a single Library for a specific Boost version"""

    model = Library
    template_name = "libraries/detail.html"

    def get_object(self):
        version_slug = self.kwargs.get("version_slug")
        slug = self.kwargs.get("slug")

        if not LibraryVersion.objects.filter(
            version__slug=version_slug, library__slug=slug
        ).exists():
            raise Http404("No library found matching the query")

        try:
            obj = self.get_queryset().get(slug=slug)
        except self.model.DoesNotExist:
            raise Http404("No library found matching the query")
        return obj

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        context = self.get_context_data(object=self.object)
        context["closed_prs_count"] = self.get_closed_prs_count(self.object)
        context["open_issues_count"] = self.get_open_issues_count(self.object)
        context["version"] = self.get_version()
        return self.render_to_response(context)

    def get_closed_prs_count(self, obj):
        return PullRequest.objects.filter(library=obj, is_open=True).count()

    def get_open_issues_count(self, obj):
        return Issue.objects.filter(library=obj, is_open=True).count()

    def get_version(self):
        version_slug = self.kwargs.get("version_slug")
        try:
            return Version.objects.get(slug=version_slug)
        except Version.DoesNotExist:
            logger.info("libraries_by_version_detail_view_version_not_found")
            raise Http404("No library for this version found matching the query")


class LibraryByCategory(CategoryMixin, ListView):
    """List all of our libraries in a certain category"""

    paginate_by = 25
    template_name = "libraries/list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        category_slug = self.kwargs.get("category")
        if category_slug:
            try:
                category = Category.objects.get(slug=category_slug)
                context["category"] = category
            except Category.DoesNotExist:
                logger.info("libraries_by_category_view_category_not_found")
        return context

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

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        context = self.get_context_data(object=self.object)
        context["closed_prs_count"] = self.get_closed_prs_count(self.object)
        context["open_issues_count"] = self.get_open_issues_count(self.object)
        return self.render_to_response(context)

    def get_closed_prs_count(self, obj):
        return PullRequest.objects.filter(library=obj, is_open=True).count()

    def get_open_issues_count(self, obj):
        return Issue.objects.filter(library=obj, is_open=True).count()
