import datetime
import structlog

from dateutil.relativedelta import relativedelta
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import DetailView, ListView
from django.views.generic.edit import FormMixin

from versions.models import Version
from .forms import VersionSelectionForm
from .github import GithubAPIClient
from .mixins import VersionAlertMixin
from .models import Category, CommitData, Library, LibraryVersion

logger = structlog.get_logger()


class LibraryList(VersionAlertMixin, ListView):
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
        context["categories"] = self.get_categories(context["version"])
        context["versions"] = Version.objects.active().order_by("-release_date")
        context["library_list"] = self.get_queryset()
        return context

    def get_categories(self, version=None):
        return (
            Category.objects.filter(libraries__versions=version)
            .distinct()
            .order_by("name")
        )


class LibraryListMini(LibraryList):
    """Flat list version of LibraryList"""

    template_name = "libraries/flat_list.html"


class LibraryListByCategory(LibraryList):
    """List all Boost libraries sorted by Category."""

    template_name = "libraries/category_list.html"

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


class LibraryDetail(FormMixin, DetailView):
    """Display a single Library in insolation"""

    form_class = VersionSelectionForm
    model = Library
    template_name = "libraries/detail.html"

    def get_context_data(self, **kwargs):
        """Set the form action to the main libraries page"""
        context = super().get_context_data(**kwargs)

        # Get fields related to Boost versions
        context["version"] = self.get_version()
        latest_version = Version.objects.most_recent()
        context["latest_version"] = latest_version
        context["versions"] = (
            Version.objects.active()
            .filter(library_version__library=self.object)
            .distinct()
            .order_by("-release_date")
        )

        # Show an alert if the user is on an older version
        if context["version"] != latest_version:
            context["version_alert"] = True
            context["latest_library_version"] = self.get_current_library_version(
                context["version"]
            )
        else:
            context["version_alert"] = False

        # Get general data and version-sensitive data
        context["documentation_url"] = self.get_documentation_url()
        context["github_url"] = self.get_github_url(context["version"])
        context["maintainers"] = self.get_maintainers(context["version"])

        # Populate the commit graphs
        context["commit_data_annual"] = self.get_commit_data_annual()
        context["commit_data_last_12_months"] = self.get_commit_data_last_12_months()

        # Populate the library description
        client = GithubAPIClient(repo_slug=self.object.github_repo)
        context["description"] = self.object.get_description(
            client, tag=context["version"].name
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

    def _prepare_commit_data(self, commit_data, data_type):
        commit_data_list = []
        for data in commit_data:
            if data_type == "annual":
                year = data["date"]
                date = datetime.date(year, 1, 1)
            else:  # Assuming monthly data
                date = data["date"]

            commit_count = data["commit_count"]
            commit_data_list.append({"date": date, "commit_count": commit_count})

        return commit_data_list

    def get_commit_data_annual(self):
        """Retrieve number of commits to the library per year."""
        if not self.object.commit_data.exists():
            return []

        # Get the first and last commit dates to determine the range of years
        first_commit = self.object.commit_data.earliest("month_year")
        first_year = first_commit.month_year.year
        current_year = datetime.date.today().year
        years = list(range(first_year, current_year + 1))

        # For years there were no commits, return the year and the 0 count
        commit_data_annual = {year: 0 for year in years}
        actual_data = dict(
            CommitData.objects.get_annual_commit_data_for_library(
                self.object
            ).values_list("year", "commit_count")
        )
        commit_data_annual.update(actual_data)
        prepared_commit_data = [
            {"date": year, "commit_count": count}
            for year, count in commit_data_annual.items()
        ]
        # Sort the data by date
        prepared_commit_data.sort(key=lambda x: x["date"])
        return self._prepare_commit_data(prepared_commit_data, "annual")

    def get_commit_data_last_12_months(self):
        """Retrieve the number of commits per month for the last year."""
        if not self.object.commit_data.exists():
            return []

        # Generate default dict of last 12 months with 0 commits so we still see
        # months with no commits
        today = datetime.date.today()
        months = [(today - relativedelta(months=i)).replace(day=1) for i in range(12)]
        commit_data_monthly = {month: 0 for month in months}

        # Update dict with real data from the database.
        actual_data = dict(
            CommitData.objects.get_commit_data_for_last_12_months_for_library(
                self.object
            ).values_list("month_year", "commit_count")
        )
        commit_data_monthly.update(actual_data)
        prepared_commit_data = [
            {"date": month, "commit_count": count}
            for month, count in commit_data_monthly.items()
        ]
        # Sort the data by date
        prepared_commit_data.sort(key=lambda x: x["date"])
        result = self._prepare_commit_data(prepared_commit_data, "monthly")
        return result

    def get_current_library_version(self, version):
        """Return the library-version for the latest version of Boost"""
        # Avoid raising an error if the library has been removed from the latest version
        return LibraryVersion.objects.filter(
            library=self.object, version=version
        ).first()

    def get_documentation_url(self):
        """Return the URL for the link to the external Boost documentation."""
        obj = self.get_object()
        version = self.get_version()
        try:
            library_version = LibraryVersion.objects.get(library=obj, version=version)
            return library_version.documentation_url
        except LibraryVersion.DoesNotExist:
            logger.exception(
                "library_detail_view_library_version_does_not_exist",
                library_slug=obj.slug,
                version_slug=version.slug,
            )
            return None

    def get_github_url(self, version):
        """Get the GitHub URL for the current library."""
        try:
            library_version = LibraryVersion.objects.get(
                library=self.object, version=version
            )
            return library_version.library_repo_url_for_version
        except LibraryVersion.DoesNotExist:
            # This should never happen because it should be caught in get_object
            return self.object.github_url

    def get_maintainers(self, version):
        """Get the maintainers for the current LibraryVersion."""
        obj = self.get_object()
        library_version = LibraryVersion.objects.get(library=obj, version=version)
        return library_version.maintainers.all()

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
