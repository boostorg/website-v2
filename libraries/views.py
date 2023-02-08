import structlog

from django.http import Http404
from django.shortcuts import redirect
from django.views.generic import DetailView, ListView, RedirectView
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

    def get_queryset(self):
        queryset = super().get_queryset()
        version = Version.objects.most_recent()
        return (
            super().get_queryset().filter(library_version__version=version).distinct()
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


class LibraryByVersion(CategoryMixin, FormMixin, ListView):
    """List all of our libraries for a specific Boost version by name"""

    form_class = LibraryForm
    paginate_by = 25
    queryset = (
        Library.objects.prefetch_related("authors", "categories").all().order_by("name")
    )
    template_name = "libraries/list.html"

    def get_queryset(self):
        queryset = super().get_queryset()
        version_slug = self.kwargs.get("version_slug")
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


class LibraryByVersionDetail(CategoryMixin, DetailView):
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
        except queryset.model.DoesNotExist:
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
        if version_slug:
            try:
                return Version.objects.get(slug=version_slug)
            except Version.DoesNotExist:
                logger.info("libraries_by_version_detail_view_version_not_found")
                raise Http404("No object found matching the query")
        else:
            return Version.objects.most_recent()


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


class LibraryByCategory(RedirectView):
    """List all of our libraries in a certain category"""

    permanent = False
    query_string = True
    pattern_name = "libraries-by-version-by-category"

    def get_redirect_url(self, *args, **kwargs):
        category_slug = self.kwargs.get("category")
        version = Version.objects.most_recent()
        return super().get_redirect_url(
            version_slug=version.slug, category=category_slug
        )


class LibraryVersionByCategory(CategoryMixin, ListView):
    """List all of our libraries in a certain category"""

    paginate_by = 25
    template_name = "libraries/list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        category_slug = self.kwargs.get("category")
        version_slug = self.kwargs.get("version_slug")

        try:
            version = Version.objects.get(slug=version_slug)
            context["version"] = version
        except Version.DoesNotExist:
            raise Http404("No library found matching the query")

        if category_slug:
            try:
                category = Category.objects.get(slug=category_slug)
                context["category"] = category
            except Category.DoesNotExist:
                logger.info("libraries_by_category_view_category_not_found")
        return context

    def get_queryset(self):
        category = self.kwargs.get("category")
        version_slug = self.kwargs.get("version_slug")

        return (
            Library.objects.prefetch_related("categories")
            .filter(
                categories__slug=category,
                versions__library_version__version__slug=version_slug,
            )
            .order_by("name")
            .distinct()
        )


class LibraryDetail(RedirectView):
    """
    Redirect a request for a generic library to the most recent Boost version
    of that library.
    """

    permanent = False
    query_string = True
    pattern_name = "libraries-by-version-detail"

    def get_redirect_url(self, *args, **kwargs):
        version = Version.objects.most_recent()
        return super().get_redirect_url(version_slug=version.slug, slug=kwargs["slug"])
