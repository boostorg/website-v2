import structlog

from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import DetailView, ListView
from django.views.generic.edit import FormMixin

from versions.models import Version
from .forms import VersionSelectionForm
from .models import Category, Issue, Library, LibraryVersion, PullRequest

logger = structlog.get_logger()


class CategoryMixin:
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = Category.objects.all().order_by("name")
        return context


class LibraryList(CategoryMixin, ListView):
    """List all of our libraries for a specific Boost version, or default
    to the current version."""

    queryset = (
        Library.objects.prefetch_related("authors", "categories").all().order_by("name")
    ).distinct()
    template_name = "libraries/list.html"

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.GET.copy()

        # default to the most recent version
        if "version" not in params:
            params["version"] = Version.objects.most_recent().slug

        queryset = queryset.filter(library_version__version__slug=params["version"])

        # avoid attempting to look up libraries with blank categories
        if "category" in params and params["category"] != "":
            queryset = queryset.filter(categories__slug=params["category"])

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if "category" in self.request.GET and self.request.GET["category"] != "":
            context["category"] = Category.objects.get(
                slug=self.request.GET["category"]
            )
        if "version" in self.request.GET:
            context["version"] = Version.objects.get(slug=self.request.GET["version"])
        else:
            context["version"] = Version.objects.most_recent()
        context["versions"] = Version.objects.active().order_by("-release_date")
        context["library_list"] = self.get_queryset()
        return context


class LibraryListMini(LibraryList):
    """Flat list version of LibraryList"""

    template_name = "libraries/list.html"


class LibraryListByCategory(LibraryList):
    """List all Boost libraries sorted by Category."""

    template_name = "libraries/list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["by_category"] = True
        context["library_list"] = self.get_results_by_category()
        return context

    def get_results_by_category(self):
        queryset = super().get_queryset()
        results_by_category = []
        for category in Category.objects.all().order_by("name"):
            results_by_category.append(
                {
                    "category": category,
                    "libraries": queryset.filter(categories=category).order_by("name"),
                }
            )
        return results_by_category


class LibraryListByCategoryMini(LibraryListByCategory):
    """Flat list version of LibraryListByCategory"""

    template_name = "libraries/list.html"


class LibraryDetail(CategoryMixin, FormMixin, DetailView):
    """Display a single Library in insolation"""

    form_class = VersionSelectionForm
    model = Library
    template_name = "libraries/detail.html"

    def get_context_data(self, **kwargs):
        """Set the form action to the main libraries page"""
        context = super().get_context_data(**kwargs)
        context["closed_prs_count"] = self.get_closed_prs_count(self.object)
        context["open_issues_count"] = self.get_open_issues_count(self.object)
        context["version"] = self.get_version()
        context["maintainers"] = self.get_maintainers(context["version"])
        context["versions"] = (
            Version.objects.active()
            .filter(library_version__library=self.object)
            .distinct()
            .order_by("-release_date")
        )
        return context

    def get_object(self):
        """Get the current library object from the slug in the URL.
        If present, use the version_slug to get the right LibraryVersion of the library.
        Otherwise, default to the most recent version."""
        slug = self.kwargs.get("slug")
        version = self.get_version()

        if not LibraryVersion.objects.filter(
            version=version, library__slug=slug
        ).exists():
            raise Http404("No library found matching the query")

        try:
            obj = self.get_queryset().get(slug=slug)
        except self.model.DoesNotExist:
            raise Http404("No library found matching the query")
        return obj

    def get_closed_prs_count(self, obj):
        """Get the number of closed pull requests for the current library."""
        return PullRequest.objects.filter(library=obj, is_open=True).count()

    def get_maintainers(self, version):
        """Get the maintainers for the current LibraryVersion."""
        obj = self.get_object()
        library_version = LibraryVersion.objects.get(library=obj, version=version)
        return library_version.maintainers.all()

    def get_open_issues_count(self, obj):
        """Get the number of open issues for the current library."""
        return Issue.objects.filter(library=obj, is_open=True).count()

    def get_version(self):
        """Get the version of Boost for the library we're currently looking at."""
        version_slug = self.kwargs.get("version_slug")
        if version_slug:
            return get_object_or_404(Version, slug=version_slug)
        else:
            return Version.objects.most_recent()

    def post(self, request, *args, **kwargs):
        """User has submitted a form and will be redirected to the right record."""
        self.object = self.get_object()
        form = self.get_form()
        if form.is_valid():
            version = form.cleaned_data["version"]
            return redirect(
                "library-detail-by-version",
                version_slug=version.slug,
                slug=self.object.slug,
            )
        else:
            logger.info("library_list_invalid_version")
        return super().get(request)
