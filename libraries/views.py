import datetime
import structlog

from django.contrib import messages
from django.db.models import Prefetch
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import DetailView, ListView, FormView, TemplateView

from core.githubhelper import GithubAPIClient
from core.mixins import V3Mixin
from versions.exceptions import BoostImportedDataException
from versions.models import Version

from .constants import README_MISSING
from .forms import CommitAuthorEmailForm
from .mixins import VersionAlertMixin, BoostVersionMixin, ContributorMixin
from .models import (
    Category,
    Library,
    LibraryVersion,
    CommitAuthorEmail,
)
from .utils import (
    get_view_from_cookie,
    set_view_in_cookie,
    get_prioritized_library_view,
    determine_selected_boost_version,
    set_selected_boost_version,
    get_documentation_url,
    get_documentation_url_redirect,
    get_prioritized_version,
    get_version_from_cookie,
    get_commit_data_by_release_for_library,
    commit_data_to_stats_bars,
    group_library_version_by_tier,
)
from .constants import LATEST_RELEASE_URL_PATH_STR

logger = structlog.get_logger()


class LibraryListDispatcher(View):
    def dispatch(self, request, *args, **kwargs):
        if view_str := request.GET.get("view", None):
            return redirect(
                reverse(
                    "libraries-list",
                    kwargs={
                        "version_slug": self.kwargs.get("version_slug"),
                        "library_view_str": view_str,
                    },
                )
            )
        view_str = self.kwargs.get("library_view_str")
        if view_str == "list":
            view = LibraryVertical.as_view()
        elif view_str == "categorized":
            view = LibraryCategorized.as_view()
        elif view_str == "grading":
            view = LibraryByTier.as_view()
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


class LibraryListBase(BoostVersionMixin, V3Mixin, VersionAlertMixin, ListView):
    """Based on LibraryVersion, list all of our libraries in grid format for a specific
    Boost version, or default to the current version."""

    queryset = LibraryVersion.objects.prefetch_related(
        "authors", "library", "library__categories"
    ).defer("data")
    ordering = "library__name"
    template_name = "libraries/grid_list.html"
    v3_template_name = "v3/library_page.html"

    def get_v3_context_data(self, **kwargs):
        context = {}
        cpp_options = [
            ("all", "All"),
            ("cpp03", "C++03"),
            ("cpp11", "C++11"),
            ("cpp14", "C++14"),
            ("cpp17", "C++17"),
            ("cpp20", "C++20"),
            ("cpp23", "C++23"),
        ]
        context["library_filter_fields"] = [
            {
                "type": "dropdown",
                "name": "view",
                "label": "View",
                "options": [
                    ("list", "List"),
                    ("grid", "Grid"),
                    ("categorized", "Category"),
                    ("grading", "Grading"),
                ],
                "selected": self.kwargs.get("library_view_str"),
                "width": "narrow",
            },
            {
                "type": "dropdown",
                "name": "grading",
                "label": "Grading",
                "options": [
                    ("all", "All"),
                    ("flagship", "Flagship"),
                    ("core", "Core"),
                    ("deprecated", "Deprecated"),
                    ("legacy", "Legacy"),
                ],
                "selected": "all",
                "width": "wide",
            },
            {
                "type": "dropdown",
                "name": "min_cpp",
                "label": "Min. C++ Version",
                "options": cpp_options,
                "selected": "all",
                "width": "narrow",
            },
            {
                "type": "dropdown",
                "name": "max_cpp",
                "label": "Max. C++ Version",
                "options": cpp_options,
                "selected": "all",
                "width": "narrow",
            },
            {
                "type": "combo_multi",
                "name": "category",
                "label": "Category",
                "options": [
                    ("algorithms", "Algorithms"),
                    ("asynchronous", "Asynchronous"),
                    ("awaitables", "Awaitables"),
                    ("containers", "Containers"),
                    ("coroutines", "Coroutines"),
                    ("correctness", "Correctness"),
                    # More dummy data to show scrollbar
                    ("data_processing", "Data processing"),
                    ("debugging", "Debugging"),
                    ("file_systems", "File systems"),
                    ("formatting", "Formatting"),
                    ("graphics", "Graphics"),
                ],
                "width": "wide",
                "placeholder": "Search",
            },
            {
                "type": "dropdown",
                "name": "sort",
                "label": "Sort by",
                "options": [
                    ("alphabetical", "Alphabetical"),
                    ("popular", "Most Popular"),
                    ("updated", "Recently Updated"),
                    ("release", "Release Date"),
                ],
                "selected": "alphabetical",
            },
        ]
        context["library_view_str"] = self.kwargs.get("library_view_str")
        return context

    def render_v3_response(self):
        """Render the v3 template through Django's standard TemplateView pipeline."""
        context = self.get_context_data(
            **self.get_v3_context_data(), object_list=self.get_queryset()
        )
        return self.render_to_response(context)

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
        context = super().get_context_data(**kwargs)
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


class LibraryByTier(LibraryListBase):
    """List all libraries sorted by Tier/Grade"""

    template_name = "libraries/categorized_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["library_versions_by_category"] = self.get_results_by_tier(
            version=context.get("selected_version")
        )
        return context

    def get_results_by_tier(self, version: Version | None):
        if not version:
            version = Version.objects.latest()
        library_versions = (
            LibraryVersion.objects.order_by("library__name")
            .filter(version=version)
            .prefetch_related("library")
        )

        flagship, core, other = group_library_version_by_tier(library_versions)

        return [
            {
                "category": "Flagship",
                "library_version_list": flagship,
            },
            {
                "category": "Core",
                "library_version_list": core,
            },
            {
                "category": "Other",
                "library_version_list": other,
            },
        ]


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

        commit_data = get_commit_data_by_release_for_library(self.object)
        context["commit_data_by_release"] = commit_data
        context["library_commits_stats_bars"] = commit_data_to_stats_bars(
            commit_data[-10:] if len(commit_data) > 10 else commit_data
        )
        try:
            context["dependency_diff"] = self.get_dependency_diff(library_version)
        except BoostImportedDataException:
            logger.warning("Library version dependencies not set, need importing.")
            context["dependency_diff"] = {}
            context["dependencies_not_calculated"] = True

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
        if not version_slug:
            version_slug = get_version_from_cookie(self.request)
        if not version_slug or version_slug == LATEST_RELEASE_URL_PATH_STR:
            return Version.objects.most_recent()
        return get_object_or_404(Version, slug=version_slug)

    def dispatch(self, request, *args, **kwargs):
        """Redirect to the documentation page, if configured to."""
        if self.redirect_to_docs:
            try:
                library_version = LibraryVersion.objects.get(
                    library__slug=self.kwargs.get("library_slug"),
                    version=self.get_version(),
                )
            except LibraryVersion.DoesNotExist:
                # account for the library not yet being available in this version
                return redirect(
                    "library-detail-version-missing",
                    library_slug=self.kwargs.get("library_slug"),
                    version_slug=get_prioritized_version(request),
                )
            return redirect(
                get_documentation_url_redirect(
                    library_version,
                    latest=self.get_version() == Version.objects.most_recent(),
                )
            )
        response = super().dispatch(request, *args, **kwargs)
        set_selected_boost_version(
            self.kwargs.get("version_slug", LATEST_RELEASE_URL_PATH_STR), response
        )
        return response


class LibraryMissingVersionView(BoostVersionMixin, DetailView):
    """Display a missing library version page with proper context"""

    model = Library
    template_name = "libraries/missing_version.html"
    slug_url_kwarg = "library_slug"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["library_view_str"] = get_prioritized_library_view(self.request)
        return context


class CommitAuthorEmailCreateView(FormView):
    template_name = "libraries/profile_commit_email_address_form.html"
    form_class = CommitAuthorEmailForm

    def post(self, request, *args, **kwargs):
        form = self.form_class(request.POST)
        if not form.is_valid():
            return self.form_invalid(form)

        email = form.cleaned_data["email"]
        commit_author_email = get_object_or_404(CommitAuthorEmail, email=email)
        commit_email_addresses = commit_author_email.trigger_verification_email(request)

        return TemplateResponse(
            request,
            "libraries/profile_commit_email_addresses.html",
            {"commit_email_addresses": commit_email_addresses},
        )

    def form_invalid(self, form):
        context = self.get_context_data(form=form)
        return self.render_to_response(context, status=422)


class VerifyCommitEmailView(TemplateView):
    """
    View to verify commit email addresses.
    This is used to ensure that commit authors have verified their email addresses.
    """

    template_name = "libraries/profile_confirm_email_address.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        token = self.kwargs.get("token")
        commit_author_email = (
            CommitAuthorEmail.objects.filter(
                claim_hash=token,
                claim_hash_expiration__gt=timezone.now(),
                claim_verified=False,
            )
            .prefetch_related("author")
            .first()
        )
        if not commit_author_email:
            context["reason_failed"] = (
                "No valid commit author found or the token has expired. Please request "
                "a new verification email."
            )
        else:
            commit_author_email.claim_hash_expiration = timezone.now()
            commit_author_email.claim_verified = True
            commit_author_email.author.user = self.request.user
            commit_author_email.author.save()
            commit_author_email.save()
            context["commit_email"] = commit_author_email.email
            context["confirmed"] = True

        return context


class CommitEmailResendView(TemplateView):
    def post(self, request, *args, **kwargs):
        commit_author_email = (
            CommitAuthorEmail.objects.filter(
                claim_hash=self.kwargs.get("claim_hash"),
                claim_verified=False,
                author__user=self.request.user,
            )
            .prefetch_related("author")
            .first()
        )
        commit_author_email.trigger_verification_email(request)

        return HttpResponse('<i class="fa-solid fa-envelope-circle-check"></i>')
