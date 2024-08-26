import datetime

import structlog
from dateutil.relativedelta import relativedelta
from django.contrib import messages
from django.db.models import Count
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import DetailView, ListView
from django.views.generic.edit import FormMixin

from core.githubhelper import GithubAPIClient
from versions.models import Version

from .forms import VersionSelectionForm
from .mixins import VersionAlertMixin
from .models import Category, CommitData, Library, LibraryVersion
from .utils import redirect_to_view_with_params

SELECTED_BOOST_VERSION_COOKIE_NAME = "boost_version"
SELECTED_LIBRARY_VIEW_COOKIE_NAME = "library_view"

logger = structlog.get_logger()


class LibraryList(VersionAlertMixin, ListView):
    """List all of our libraries for a specific Boost version, or default
    to the current version."""

    queryset = (
        (
            Library.objects.prefetch_related("authors", "categories")
            .all()
            .order_by("name")
        )
        .defer("data")
        .distinct()
    )
    template_name = "libraries/list.html"

    def get_selected_boost_version(self) -> str:
        """Get the selected version from the cookies."""
        valid_versions = Version.objects.version_dropdown_strict()
        version_slug = self.request.COOKIES.get(
            SELECTED_BOOST_VERSION_COOKIE_NAME, None
        )

        if version_slug is None:
            version_slug = self.request.GET.get("version", None)

        if version_slug in [v.slug for v in valid_versions]:
            return version_slug
        else:
            logger.warning(f"Invalid version slug in cookies: {version_slug}")
            return None

    def set_selected_boost_version(self, response, version: str) -> None:
        """Set the selected version in the cookies."""
        valid_versions = Version.objects.version_dropdown_strict()

        if version in [v.slug for v in valid_versions]:
            response.set_cookie(SELECTED_BOOST_VERSION_COOKIE_NAME, version)
        else:
            logger.warning(f"Attempted to set invalid version slug: {version}")

    def get_selected_library_view(self) -> str:
        """Get the user's preferred view for the libraries page."""
        return self.request.COOKIES.get(SELECTED_LIBRARY_VIEW_COOKIE_NAME)

    def set_selected_library_view(
        self, response, view: str, *, clear: bool = False
    ) -> str:
        """Set the user's preferred view for the libraries page."""
        if clear:
            response.delete_cookie(SELECTED_LIBRARY_VIEW_COOKIE_NAME)
        else:
            response.set_cookie(SELECTED_LIBRARY_VIEW_COOKIE_NAME, view)
            return view

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.GET.copy()

        # If the user has selected a version, fetch it from the cookies.
        selected_boost_version = self.get_selected_boost_version()
        if selected_boost_version != params.get("version", None):
            params["version"] = selected_boost_version

        # default to the most recent version
        if "version" not in params:
            # If no version is specified, show the most recent version.
            version = Version.objects.most_recent()
            if version:
                params["version"] = version.slug
            else:
                # Add a message that no data has been imported
                messages.add_message(
                    self.request,
                    messages.WARNING,
                    "No data has been imported yet. Please check back later.",
                )
                return Library.objects.none()

        queryset = queryset.filter(library_version__version__slug=params["version"])

        # avoid attempting to look up libraries with blank categories
        if "category" in params and params["category"] != "":
            queryset = queryset.filter(categories__slug=params["category"])

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Handle the case where data hasn't been imported yet
        version = Version.objects.most_recent()
        if not version:
            context.update(
                {
                    "category": None,
                    "version": None,
                    "categories": Category.objects.none(),
                    "versions": Version.objects.none(),
                    "library_list": Library.objects.none(),
                }
            )
            return context

        if "category" in self.request.GET and self.request.GET["category"] != "":
            context["category"] = Category.objects.get(
                slug=self.request.GET["category"]
            )
        if "version" in self.request.GET:
            context["version"] = Version.objects.get(slug=self.request.GET["version"])
        else:
            context["version"] = Version.objects.most_recent()
        context["categories"] = self.get_categories(context["version"])
        context["versions"] = self.get_versions()
        context["library_list"] = self.get_queryset()
        return context

    def get_categories(self, version=None):
        return (
            Category.objects.filter(libraries__versions=version)
            .distinct()
            .order_by("name")
        )

    def get_versions(self):
        """
        Return a queryset of all versions to display in the version dropdown.
        """
        versions = Version.objects.version_dropdown().order_by("-name")

        # Annotate each version with the number of libraries it has
        versions = versions.annotate(
            library_count=Count("library_version", distinct=True)
        ).order_by("-name")

        # Filter out versions with no libraries
        versions = versions.filter(library_count__gt=0)

        most_recent_version = Version.objects.most_recent()

        # Confirm the most recent v is in the queryset, even if it has no libraries
        if most_recent_version not in versions:
            versions = versions | Version.objects.filter(pk=most_recent_version.pk)

        # Manually exclude the master and develop branches.
        versions = versions.exclude(name__in=["develop", "master", "head"])
        return versions

    def get_version_request_from_url(self):
        return self.request.GET.get("version")

    def view_route_from_url(self):
        path_info = self.request.path_info

        # Determine the route name based on the URL.
        if "/by-category/" in path_info:
            route_name = "libraries-by-category"
        elif "/mini/" in path_info:
            route_name = "libraries-mini"
        else:
            route_name = "libraries"

        return route_name

    def dispatch(self, request, *args, **kwargs):
        """Set the selected version in the cookies."""
        response = super().dispatch(request, *args, **kwargs)

        # If the user has requested a reset, clear the session value.
        if "reset_view" in request.GET:
            self.set_selected_library_view(response, "", clear=True)

        # Determine the route name based on the URL.
        route_name = self.view_route_from_url()
        if route_name in ["libraries-mini", "libraries-by-category"]:
            self.set_selected_library_view(response, route_name)

        redirect_to_version = self.get_selected_boost_version()
        redirect_to_route = self.get_selected_library_view()
        route_in_url = self.view_route_from_url()
        version_in_url = self.get_version_request_from_url()

        # If the user has a preferred view, use that.
        if redirect_to_route and route_in_url != redirect_to_route:
            if "reset_view" not in request.GET:
                self.set_selected_library_view(response, route_name)
                return redirect(redirect_to_route)
            route_name = redirect_to_route

        # Set the cookie value to the version in the URL.
        if version_in_url:
            self.set_selected_boost_version(response, version_in_url)
        else:
            # If no version is present in the URL, default to the cookie value.
            if redirect_to_version:
                # Construct the URL with the version from the cookie.
                current_category = request.GET.get("category", "")
                reset_view = "reset_view" in request.GET

                query_params = {
                    "category": current_category,
                    "version": redirect_to_version,
                }
                if reset_view:
                    query_params.update(reset_view="1")

                if not current_category:
                    del query_params["category"]

                # Redirect to the correct view with the correct version.
                redirect_to_route = self.get_selected_library_view()
                route_name = redirect_to_route if redirect_to_route else route_name

                return redirect_to_view_with_params(route_name, kwargs, query_params)

        return response


class LibraryListMini(LibraryList):
    """Flat list version of LibraryList"""

    template_name = "libraries/flat_list.html"


class LibraryListByCategory(LibraryList):
    """List all Boost libraries sorted by Category."""

    template_name = "libraries/category_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
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


@method_decorator(csrf_exempt, name="dispatch")
class LibraryDetail(FormMixin, DetailView):
    """Display a single Library in insolation"""

    form_class = VersionSelectionForm
    model = Library
    template_name = "libraries/detail.html"
    redirect_to_docs = False

    def set_selected_boost_version(self, version):
        self.request.COOKIES[SELECTED_BOOST_VERSION_COOKIE_NAME] = version

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

        # Manually exclude feature branches from the version dropdown.
        context["versions"] = context["versions"].exclude(
            name__in=["develop", "master", "head"]
        )

        # Manually exclude beta releases from the version dropdown.
        context["versions"] = context["versions"].exclude(beta=True)

        # Show an alert if the user is on an older version
        if context["version"] != latest_version:
            context["version_alert"] = True
            context["latest_library_version"] = self.get_current_library_version(
                context["version"]
            )
        else:
            context["version_alert"] = False

        # Get general data and version-sensitive data
        context["documentation_url"] = self.get_documentation_url(context["version"])
        context["github_url"] = self.get_github_url(context["version"])
        context["maintainers"] = self.get_maintainers(context["version"])
        context["author_tag"] = self.get_author_tag()

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

    def get_author_tag(self):
        """Format the authors for the author meta tag in the template."""
        authors = self.object.authors.all()
        author_names = [author.get_full_name() for author in authors]
        if len(author_names) > 1:
            final_output = ", ".join(author_names[:-1]) + " and " + author_names[-1]
        else:
            final_output = author_names[0] if author_names else ""

        return final_output

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

    def get_documentation_url(self, version):
        """Get the documentation URL for the current library."""

        def find_documentation_url(version):
            obj = self.get_object()
            library_version = LibraryVersion.objects.get(library=obj, version=version)
            docs_url = version.documentation_url

            # If we know the library-version docs are missing, return the version docs
            if library_version.missing_docs:
                return docs_url
            # If we have the library-version docs and they are valid, return those
            elif library_version.documentation_url:
                return library_version.documentation_url
            # If we wind up here, return the version docs
            else:
                return docs_url

        # Get the URL for the version.
        url = find_documentation_url(version)
        # Remove the "boost_" prefix from the URL.
        url = url.replace("boost_", "")

        return url

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

    def dispatch(self, request, *args, **kwargs):
        """Redirect to the documentation page, if configured to."""
        if self.redirect_to_docs:
            return redirect(self.get_documentation_url(self.get_version()))

        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        """User has submitted a form and will be redirected to the right record."""
        self.object = self.get_object()
        form = self.get_form()
        if form.is_valid():
            version = form.cleaned_data["version"]
            self.set_selected_boost_version(version.slug)
            return redirect(
                "library-detail-by-version",
                version_slug=version.slug,
                slug=self.object.slug,
            )
        else:
            logger.info("library_list_invalid_version")
        return super().get(request)
