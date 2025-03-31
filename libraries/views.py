import datetime

from django.contrib import messages
from django.db.models import F, Count, Prefetch
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import DetailView, ListView

from core.githubhelper import GithubAPIClient
from versions.models import Version

from .constants import README_MISSING
from .mixins import VersionAlertMixin, BoostVersionMixin, ContributorMixin
from .models import (
    Category,
    Library,
    LibraryVersion,
)
from .utils import (
    get_view_from_cookie,
    set_view_in_cookie,
    get_prioritized_library_view,
    determine_selected_boost_version,
    set_selected_boost_version,
    get_documentation_url,
)
from .constants import LATEST_RELEASE_URL_PATH_STR


class LibraryListDispatcher(View):
    def dispatch(self, request, *args, **kwargs):
        view_str = self.kwargs.get("library_view_str")
        if view_str == "list":
            view = LibraryVertical.as_view()
        elif view_str == "categorized":
            view = LibraryCategorized.as_view()
        else:
            # covers both /libraries and /libraries/.../grid[/...]
            view = LibraryListBase.as_view()
        version_str = (
            determine_selected_boost_version(
                self.kwargs.get("version_slug"), self.request
            )
            or LATEST_RELEASE_URL_PATH_STR
        )
        if not self.kwargs.get("version_slug"):
            self.kwargs["version_slug"] = version_str
        return view(request, *args, **self.kwargs)  # , *args, **kwargs)


class LibraryListBase(BoostVersionMixin, VersionAlertMixin, ListView):
    """Based on LibraryVersion, list all of our libraries in grid format for a specific
    Boost version, or default to the current version."""

    queryset = LibraryVersion.objects.prefetch_related(
        "authors", "library", "library__categories"
    ).defer("data")
    ordering = "library__name"
    template_name = "libraries/grid_list.html"

    def get_queryset(self):
        queryset = super().get_queryset()
        version_slug = determine_selected_boost_version(
            self.kwargs.get("version_slug"), self.request
        )
        if version_slug == LATEST_RELEASE_URL_PATH_STR:
            version = Version.objects.most_recent()
            if not version:
                messages.add_message(
                    self.request,
                    messages.WARNING,
                    "No data has been imported yet. Please check back later.",
                )
                return Library.objects.none()
            version_slug = version.slug

        version_filter_args = {"version__slug": version_slug}

        no_category_filtering_views = ["categorized"]
        if (
            self.kwargs.get("category_slug")
            and self.kwargs.get("library_view_str") not in no_category_filtering_views
        ):
            version_filter_args["library__categories__slug"] = self.kwargs.get(
                "category_slug"
            )

        return queryset.filter(**version_filter_args)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**self.kwargs)
        context["categories"] = self.get_categories(context["selected_version"])
        # todo: add tests for sort order
        if self.kwargs.get("category_slug"):
            context["category"] = Category.objects.get(
                slug=self.kwargs.get("category_slug")
            )

        return context

    def get_categories(self, version=None):
        return (
            Category.objects.filter(libraries__versions=version)
            .distinct()
            .order_by("name")
        )

    def dispatch(self, request, *args, **kwargs):
        """Set the selected version in the cookies."""
        response = super().dispatch(request, *args, **kwargs)
        set_selected_boost_version(self.kwargs.get("version_slug"), response)
        view = get_prioritized_library_view(request)
        if request.resolver_match.view_name == "libraries":
            # todo: remove the following migration block some time after March 1st 2025
            def update_deprecated_cookie_view(cookie_view, response):
                deprecated_views = {
                    "libraries-mini": "list",
                    "libraries-grid": "grid",
                    "libraries-by-category": "categorized",
                }
                if cookie_view in deprecated_views:
                    cookie_view = deprecated_views[cookie_view]
                    set_view_in_cookie(response, cookie_view)
                return cookie_view

            view = update_deprecated_cookie_view(view, response)
            # todo: end of migration block

            # set the cookie in case it has changed
            set_view_in_cookie(response, view)
            redirect_args = {
                "version_slug": self.kwargs.get("version_slug"),
                "library_view_str": view,
            }
            if self.kwargs.get("category_slug"):
                redirect_args["category_slug"] = self.kwargs.get("category_slug")
            return redirect("libraries-list", **redirect_args)

        if view != get_view_from_cookie(request):
            set_view_in_cookie(response, view)

        return response


class LibraryVertical(LibraryListBase):
    """Flat list version of LibraryList"""

    template_name = "libraries/vertical_list.html"


class LibraryCategorized(LibraryListBase):
    """List all Boost libraries sorted by Category."""

    template_name = "libraries/categorized_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["library_versions_by_category"] = self.get_results_by_category(
            version=context.get("selected_version")
        )
        return context

    def get_results_by_category(self, version: Version | None):
        # Define filter kwargs based on whether version is provided
        category_filter = (
            {"libraries__library_version__version": version} if version else {}
        )
        libraries_prefetch = Prefetch(
            "libraries",
            queryset=Library.objects.order_by("name").prefetch_related(
                Prefetch(
                    "library_version",
                    queryset=self.get_queryset(),
                    to_attr="prefetched_library_versions",
                )
            ),
            to_attr="prefetched_libraries",
        )

        categories = (
            Category.objects.filter(**category_filter)
            .distinct()
            .order_by("name")
            .prefetch_related(libraries_prefetch)
        )

        results_by_category = []
        for category in categories:
            library_versions = []
            for library in getattr(category, "prefetched_libraries", []):
                prefetched_versions = getattr(
                    library, "prefetched_library_versions", []
                )
                library_versions.extend(prefetched_versions)

            results_by_category.append(
                {"category": category, "library_version_list": library_versions}
            )
        return results_by_category


@method_decorator(csrf_exempt, name="dispatch")
class LibraryDetail(VersionAlertMixin, BoostVersionMixin, ContributorMixin, DetailView):
    """Display a single Library in insolation"""

    model = Library
    template_name = "libraries/detail.html"
    redirect_to_docs = False
    slug_url_kwarg = "library_slug"

    def get_context_data(self, **kwargs):
        """Set the form action to the main libraries page"""
        context = super().get_context_data(**kwargs)
        context["library_view_str"] = get_prioritized_library_view(self.request)
        # Get versions, flag when the current library isn't in each version
        context["LATEST_RELEASE_URL_PATH_NAME"] = LATEST_RELEASE_URL_PATH_STR
        if not self.object:
            raise Http404("No library found matching the query")
        try:
            library_version = LibraryVersion.objects.get(
                library=self.object, version=context["selected_version"]
            )
        except LibraryVersion.DoesNotExist:
            return context

        context["library_version"] = library_version
        context["documentation_url"] = get_documentation_url(
            library_version, context["version_str"] == LATEST_RELEASE_URL_PATH_STR
        )
        context["github_url"] = (
            library_version.library_repo_url_for_version
            if library_version
            else self.object.github_url
        )

        # Populate the commit graphs
        context["commit_data_by_release"] = self.get_commit_data_by_release()
        context["dependency_diff"] = self.get_dependency_diff(library_version)

        # Populate the library description
        client = GithubAPIClient(repo_slug=self.object.github_repo)
        context["description"] = (
            self.object.get_description(client, tag=context["selected_version"].name)
            or README_MISSING
        )
        return context

    def get_dependency_diff(self, library_version):
        diffs = library_version.version.get_dependency_diffs(
            library=library_version.library
        )
        return diffs.get(library_version.library.name, {})

    def get_commit_data_by_release(self):
        qs = (
            LibraryVersion.objects.filter(
                library=self.object,
                version__in=Version.objects.minor_versions(),
            )
            .annotate(count=Count("commit"), version_name=F("version__name"))
            .order_by("-version__name")
        )[:20]
        return [
            {
                "release": x.version_name.strip("boost-"),
                "commit_count": x.count,
            }
            for x in reversed(list(qs))
        ]

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

    def get_version(self):
        """Get the version of Boost for the library we're currently looking at."""
        version_slug = self.kwargs.get("version_slug")
        # here we need to check for not version_slug because of redirect_to_docs
        # where it's not necessarily set by the source request
        if not version_slug or version_slug == LATEST_RELEASE_URL_PATH_STR:
            return Version.objects.most_recent()
        return get_object_or_404(Version, slug=version_slug)

    def dispatch(self, request, *args, **kwargs):
        """Redirect to the documentation page, if configured to."""
        if self.redirect_to_docs:
            return redirect(
                get_documentation_url(
                    LibraryVersion.objects.get(
                        library__slug=self.kwargs.get("library_slug"),
                        version=self.get_version(),
                    ),
                    latest=True,
                )
            )
        response = super().dispatch(request, *args, **kwargs)
        set_selected_boost_version(
            self.kwargs.get("version_slug", LATEST_RELEASE_URL_PATH_STR), response
        )
        return response
