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


class LibraryList(RedirectView):
    """
    Redirect a request for the list of libraries to the list of libraries
    for the most recent version of Boost
    """

    permanent = False
    query_string = True
    pattern_name = "libraries-by-version"

    def get_redirect_url(self, *args, **kwargs):
        version = Version.objects.most_recent()
        return super().get_redirect_url(version_pk=version.pk)


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
        version_pk = self.kwargs.get("version_pk")
        return super().get_queryset().filter(library_version__version__pk=version_pk)

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
        version_pk = self.kwargs.get("version_pk")
        slug = self.kwargs.get("slug")

        if not LibraryVersion.objects.filter(
            version__pk=version_pk, library__slug=slug
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
        version_pk = self.kwargs.get("version_pk")
        if version_pk:
            try:
                return Version.objects.get(pk=version_pk)
            except Version.DoesNotExist:
                logger.info("libraries_by_version_detail_view_version_not_found")
                return
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


class LibraryDetail(RedirectView):
    """
    Redirect a request for a generic library to the most recent Boost version
    of that library.
    """

    permanent = False
    query_string = True
    pattern_name = "libraries-by-version-detail"

    def get_redirect_url(self, *args, **kwargs):
        # library = get_object_or_404(Library, slug=kwargs['slug'])
        version = Version.objects.most_recent()
        return super().get_redirect_url(version_pk=version.pk, slug=kwargs["slug"])
