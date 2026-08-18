import datetime
import uuid
from urllib.parse import urlencode, urlparse

import structlog

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
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
from waffle import flag_is_active

from core.constants import SLACK_JOIN_URL
from core.githubhelper import GithubAPIClient
from core.mixins import V3Mixin
from mailing_list.mixins import MailingListCardMixin
from core.mock_data import SharedResources
from news.services import get_library_post_cards
from users.models import User
from versions.exceptions import BoostImportedDataException
from versions.models import Version

from .constants import COMMIT_EMAIL_STALE_ACTION_ERROR, README_MISSING
from .forms import CommitAuthorEmailForm, V3CommitAuthorEmailForm
from .godbolt import build_compiler_explorer_url
from .mixins import VersionAlertMixin, BoostVersionMixin, ContributorMixin
from .models import (
    Category,
    Library,
    LibraryVersion,
    CommitAuthorEmail,
    Tier,
)
from .utils import (
    address_already_proven_by,
    apply_collective_author_overrides,
    prefer_boost_profile_links,
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
    group_libraries_by_tier,
    designed_for_html,
    benchmark_sets,
)
from .constants import LATEST_RELEASE_URL_PATH_STR

logger = structlog.get_logger()


# ── V3 context helpers ─────────────────────────────────────────────────────


def _is_boost_url(url):
    """True when `url` points at a Boost-owned location (boost.org or
    github.com/boostorg). Guards the maintainer-supplied Quick Start links so a
    stray/off-site URL falls back to the documentation link instead."""
    if not url:
        return False
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").lower()
    if host == "boost.org" or host.endswith(".boost.org"):
        return True
    if host in ("github.com", "www.github.com"):
        return parsed.path.lower().lstrip("/").startswith("boostorg/")
    return False


def _build_quick_start_links(documentation_url, links):
    """Build the Quick Start card links from website.adoc's [#links] section.

    "Common use cases" and "Code Examples" come from the maintainer's
    :common-use-case-url: / :code-example-url:. Each is used only if it is a
    valid Boost URL; otherwise it falls back to the documentation link.
    """
    links = links or {}
    result = []
    common = links.get("common_use_case_url")
    example = links.get("code_example_url")
    common_url = common if _is_boost_url(common) else documentation_url
    example_url = example if _is_boost_url(example) else documentation_url
    if common_url:
        result.append({"label": "Common use cases", "url": common_url})
    if example_url:
        result.append({"label": "Code Examples", "url": example_url})
    return result


def _build_dependencies_list(current_dependencies, version_str):
    """Build the dependencies list for the V3 dependencies card."""
    result = []
    for dep in current_dependencies:
        try:
            url = reverse(
                "library-detail",
                kwargs={"version_slug": version_str, "library_slug": dep.slug},
            )
        except Exception:
            url = "#"
        result.append({"name": dep.name, "url": url})
    return result


def _build_release_contributors(context):
    """Build the "Contributors: This Release" profile list from the context
    populated by ContributorMixin: authors + maintainers + new and returning
    commit contributors, each tagged with its display role."""
    return (
        [u.to_v3_profile_dict("Author") for u in context.get("authors", [])]
        + [u.to_v3_profile_dict("Maintainer") for u in context.get("maintainers", [])]
        + [
            a.to_v3_profile_dict("New Contributor")
            for a in context.get("top_contributors_release_new", [])
        ]
        + [
            a.to_v3_profile_dict("Contributor")
            for a in context.get("top_contributors_release_old", [])
        ]
    )


def _build_compiler_explorer_link(website_adoc, selected_version):
    """Build the "Edit in Compiler Explorer" Quick Start link from website.adoc's
    [#playground] code. Returns None when there's no playground code or godbolt
    can't produce a URL."""
    playground = website_adoc.get("playground")
    if not (playground and playground.get("code")):
        return None
    boost_version = selected_version.display_name if selected_version else ""
    url = build_compiler_explorer_url(playground["code"], boost_version)
    if not url:
        return None
    return {"label": "Edit in Compiler Explorer", "url": url}


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
        # author_details links the author's profile, which reads their routing
        # keys. The inner queryset is ordered so that its `.first()` call can
        # slice the prefetch cache: `first()` re-sorts an unordered queryset by
        # pk, and that clone drops the cache and re-queries once per card.
        Prefetch(
            "authors",
            queryset=User.objects.order_by("pk").prefetch_related(
                "profile_routing_keys"
            ),
        ),
        "library",
        "library__categories",
    ).defer("data")
    ordering = "library__name"
    template_name = "libraries/grid_list.html"
    v3_template_name = "v3/library_page.html"

    def get_v3_context_data(self, queryset=None, **kwargs):
        queryset = getattr(self, "object_list") or []
        context = super().get_v3_context_data(**kwargs)
        view_str = self.kwargs.get("library_view_str")

        cpp_options = [("all", "All")] + list(
            LibraryVersion.CPP_STANDARD_DISPLAY_NAMES.items()
        )

        tiers_present = sorted(
            {lv.library.tier for lv in (queryset or []) if lv.library.tier is not None}
        )

        grading_options = [("all", "All")] + [
            (Tier(t).label.lower(), Tier(t).label) for t in tiers_present
        ]

        category_options = [
            (c.slug, c.name) for c in self.get_categories(self._selected_version)
        ]

        request_get = self.request.GET
        selected_categories = request_get.getlist("category")

        context["library_filter_fields"] = [
            {
                "type": "dropdown",
                "name": "view",
                "label": "View",
                "options": [
                    ("list", "List"),
                    ("grid", "Card"),
                    ("categorized", "Category"),
                    ("grading", "Grading"),
                ],
                "selected": view_str,
                "default": "list",
                "width": "category",
                "deselectable": False,
                "exclude_from_clear": True,
            },
            {
                "type": "dropdown",
                "name": "grading",
                "label": "Grading",
                "options": grading_options,
                "selected": request_get.get("grading", "all"),
                "default": "all",
                "width": "wide",
                "deselectable": True,
            },
            {
                "type": "dropdown",
                "name": "min_cpp",
                "label": "Min. C++ Version",
                "options": cpp_options,
                "selected": request_get.get("min_cpp", "all"),
                "default": "all",
                "width": "narrow",
                "deselectable": True,
            },
            {
                "type": "dropdown",
                "name": "max_cpp",
                "label": "Max. C++ Version",
                "options": cpp_options,
                "selected": request_get.get("max_cpp", "all"),
                "default": "all",
                "width": "narrow",
                "deselectable": True,
            },
            {
                "type": "combo_multi",
                "name": "category",
                "label": "Category",
                "options": category_options,
                "selected_values": selected_categories,
                "width": "wide",
                "placeholder": "Search",
                "deselectable": True,
            },
            # Sort is applied client-side via libraryFilter.sortItems(); no
            # queryset.order_by() here. The default alphabetical order comes
            # from the view's `ordering = "library__name"`.
            {
                "type": "dropdown",
                "name": "sort",
                "label": "Sort by",
                "options": [
                    ("alphabetical", "Alphabetical"),
                    ("popularity", "Most Popular"),
                ],
                "selected": request_get.get("sort", "alphabetical"),
                "default": "alphabetical",
                "deselectable": True,
            },
        ]
        context["library_view_str"] = view_str
        context["library_filter_defaults"] = {
            f["name"]: f["default"]
            for f in context["library_filter_fields"]
            if "default" in f
        }
        context["library_filter_clear_url"] = reverse(
            "libraries-list",
            kwargs={
                "version_slug": self.kwargs.get("version_slug"),
                "library_view_str": "list",
            },
        )

        # Compact JSON payload for client-side filtering on list/grid views.
        context["library_dataset"] = [
            {
                "slug": lv.library.slug,
                "name": lv.library.name,
                "description": lv.description or lv.library.description or "",
                "category_slugs": [c.slug for c in lv.library.categories.all()],
                "category_names": [c.name for c in lv.library.categories.all()],
                "author_names": [
                    a.display_name for a in lv.authors.all() if a.display_name
                ],
                "cpp_min": lv.get_cpp_standard_minimum_display() or "",
                "cpp_max": lv.get_cpp_standard_maximum_display() or "",
                "tier": (
                    Tier(lv.library.tier).label.lower()
                    if lv.library.tier is not None
                    else ""
                ),
            }
            for lv in (queryset or [])
        ]
        context["library_search_query"] = self.request.GET.get("q", "")
        return context

    def _resolve_selected_version(self):
        version_slug = determine_selected_boost_version(
            self.kwargs.get("version_slug"), self.request
        )
        if version_slug == LATEST_RELEASE_URL_PATH_STR:
            return Version.objects.most_recent()
        return Version.objects.filter(slug=version_slug).first()

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
        # combine context_data kwargs and view kwargs for creating template context
        kwargs = kwargs | self.kwargs
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
        # Resolve selected_version once so get_v3_context_data can reuse it.
        self._selected_version = self._resolve_selected_version()
        response = super().dispatch(request, *args, **kwargs)
        # Set the selected version in the cookies.
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
        context["library_versions_by_category"] = self.get_results_by_tier()
        return context

    def get_results_by_tier(self):
        library_versions = self.get_queryset()
        flagship, core, other = group_libraries_by_tier(library_versions)

        return [
            {
                "category": "Flagship",
                "icon": "flag",
                "library_version_list": flagship,
            },
            {
                "category": "Core",
                "icon": None,
                "library_version_list": core,
            },
            {
                "category": "Other",
                "icon": None,
                "library_version_list": other,
            },
        ]


@method_decorator(csrf_exempt, name="dispatch")
class LibraryDetail(
    MailingListCardMixin,
    V3Mixin,
    VersionAlertMixin,
    BoostVersionMixin,
    ContributorMixin,
    DetailView,
):
    """Display a single Library in insolation"""

    model = Library
    template_name = "libraries/detail.html"
    v3_template_name = "v3/libraries/library-subpage.html"
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
            # No LibraryVersion for the selected release (e.g. viewing a version
            # older than the library's first release). Flag it so the v3 template
            # renders the empty state instead of an empty subpage.
            context["library_version_missing"] = True
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

    def get_v3_context_data(self, **kwargs):
        context = {**kwargs}

        if context.get("library_version_missing"):
            # The empty state renders a hero and nothing else, so none of the
            # card context below applies.
            return self.get_missing_version_context(context)

        version_str = context.get("version_str") or LATEST_RELEASE_URL_PATH_STR

        library_version = context.get("library_version")
        context["website_adoc"] = getattr(library_version, "website_adoc", None) or {}
        context["designed_for_html"] = designed_for_html(
            context["website_adoc"].get("designed_for")
        )
        context["benchmark_sets"] = benchmark_sets(
            context["website_adoc"].get("benchmarks")
        )
        context["slack_url"] = self.object.slack_url or SLACK_JOIN_URL

        context["category_tags_v3"] = [
            {"label": cat.name, "url": cat.get_filter_url(version_str)}
            for cat in self.object.categories.all().order_by("name")
        ]

        context["quick_start_links"] = _build_quick_start_links(
            context.get("documentation_url"),
            context["website_adoc"].get("links"),
        )
        compiler_explorer_link = _build_compiler_explorer_link(
            context["website_adoc"], context.get("selected_version")
        )
        if compiler_explorer_link:
            context["quick_start_links"].append(compiler_explorer_link)

        dep_diff = context.get("dependency_diff", {})
        context["dependencies_list"] = _build_dependencies_list(
            dep_diff.get("current_dependencies") or [],
            version_str,
        )

        context["library_posts"] = get_library_post_cards(self.object.slug, limit=3)
        context["library_posts_cta_url"] = reverse("news")

        this_release = _build_release_contributors(context)
        context["this_release_contributors"] = (
            apply_collective_author_overrides(prefer_boost_profile_links(this_release))
            or SharedResources.library_release_contributors
        )

        all_time = (
            self.build_all_contributors(
                library_version,
                context.get("authors", []),
                context.get("maintainers", []),
            )
            if library_version
            else []
        )
        context["all_time_contributors"] = (
            apply_collective_author_overrides(prefer_boost_profile_links(all_time))
            or SharedResources.library_all_contributors
        )

        context["is_flagship_lib"] = self.object.tier == Tier.FLAGSHIP
        if context["is_flagship_lib"]:
            context["library_hero_image_url_light"] = (
                SharedResources.hero_legacy_image_url_light
            )
            context["library_hero_image_url_dark"] = (
                SharedResources.hero_legacy_image_url_dark
            )
            context["hero_image_url"] = SharedResources.hero_legacy_image_url_dark
        else:
            context["library_hero_image_url_light"] = ""
            context["library_hero_image_url_dark"] = ""
            context["hero_image_url"] = ""

        return context

    def get_missing_version_context(self, context):
        """Add the copy and CTA for the "no records for this version" empty state.

        Built here rather than in the template because both the sentence and the
        CTA branch on data: a library with no releases at all has no second
        sentence and nowhere to switch to, and a library that has left Boost
        needs the last release that shipped it rather than the first.
        """
        library = self.object
        selected_version = context.get("selected_version")
        selected_is_branch = selected_version.slug in settings.BOOST_BRANCHES
        selected_label = (
            f"the {selected_version.display_name} branch"
            if selected_is_branch
            else f"Boost {selected_version.display_name}"
        )
        description = (
            f"There is no version of the {library.display_name} library for "
            f"{selected_label}."
        )

        released_versions = Version.objects.active().filter(
            library_version__library=library, beta=False, full_release=True
        )
        newest_version = released_versions.order_by("-name").first()

        left_boost = newest_version and (
            selected_is_branch
            or selected_version.cleaned_version_parts_int
            > newest_version.cleaned_version_parts_int
        )
        if left_boost:
            description += (
                f" The last release which included {library.display_name} was "
                f"{newest_version.display_name}."
            )
        elif first_version := released_versions.order_by("name").first():
            description += (
                f" The first release of {library.display_name} library was version "
                f"{first_version.display_name}."
            )
        context["library_version_missing_description"] = description

        if newest_version:
            is_latest = newest_version == Version.objects.most_recent()
            context["library_version_missing_cta_url"] = reverse(
                "library-detail",
                kwargs={
                    "version_slug": (
                        LATEST_RELEASE_URL_PATH_STR
                        if is_latest
                        else newest_version.slug
                    ),
                    "library_slug": library.slug,
                },
            )
            context["library_version_missing_cta_label"] = (
                f"Switch to latest ({newest_version.display_name})"
                if is_latest
                else f"Switch to {newest_version.display_name}"
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
        self.set_extra_context(request)
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
    Landing page for the commit email verification link.

    Behind the v3 flag, the link is only usable inside the claimant's own
    authenticated session: proving the claim takes both the token (inbox
    access) and being logged in as the account that asked. Any other
    visitor - anonymous, or a different account - gets the same generic
    failure page as an invalid token, so nothing ever happens on the
    claimant's behalf and tokens cannot be probed. GET never changes state
    (mail scanners prefetch links); the claim completes on the explicit
    POST from the confirm button.

    With the flag off, the legacy behavior is preserved untouched: the GET
    itself completes the verification and binds author.user to the visitor,
    rendered with the legacy template.
    """

    template_name = "libraries/profile_confirm_email_address.html"
    v3_template_name = "v3/libraries/commit_email_confirm.html"

    def get_template_names(self):
        if flag_is_active(self.request, "v3"):
            return [self.v3_template_name]
        return super().get_template_names()

    def _parsed_token(self):
        # the route accepts any string; a mangled link must land on the
        # generic failure page, not 500 on the UUIDField lookup
        try:
            return uuid.UUID(str(self.kwargs.get("token")))
        except (TypeError, ValueError):
            return None

    def _get_viewers_open_claim(self, for_update=False):
        if not self.request.user.is_authenticated:
            return None
        token = self._parsed_token()
        if token is None:
            return None
        queryset = CommitAuthorEmail.objects.filter(
            claim_hash=token,
            claim_hash_expiration__gt=timezone.now(),
            claim_verified=False,
            claimed_by=self.request.user,
        ).select_related("author")
        if for_update:
            queryset = queryset.select_for_update(of=("self",))
        return queryset.first()

    def _legacy_verify_context(self, context):
        # pre-v3 behavior, restored verbatim: the GET completes the
        # verification and binds the author to whoever opened the link
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if not flag_is_active(self.request, "v3"):
            return self._legacy_verify_context(context)
        context["home_url"] = "/"
        commit_author_email = self._get_viewers_open_claim()
        if commit_author_email:
            context["commit_author_email"] = commit_author_email
        elif (
            self.request.user.is_authenticated
            and self._parsed_token() is not None
            and CommitAuthorEmail.objects.filter(
                claim_hash=self._parsed_token(),
                claim_verified=True,
                claimed_by=self.request.user,
            ).exists()
        ):
            context["already_verified"] = True
        return context

    def post(self, request, *args, **kwargs):
        if not flag_is_active(request, "v3"):
            # the legacy view was GET-only
            return self.http_method_not_allowed(request, *args, **kwargs)

        # locked read: the token, claimant, expiry, and verification state
        # are re-evaluated under the row lock, so a concurrent withdraw or
        # resend can't slip between the check and verify_claim
        with transaction.atomic():
            commit_author_email = self._get_viewers_open_claim(for_update=True)
            if commit_author_email:
                attribution_bound = commit_author_email.verify_claim()

        if not commit_author_email:
            return self.get(request, *args, **kwargs)
        return self.render_to_response(
            {
                "view": self,
                "commit_email": commit_author_email.email,
                "confirmed": attribution_bound,
                "conflict": not attribution_bound,
                "home_url": "/",
            }
        )


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


def _is_htmx(request) -> bool:
    return request.headers.get("HX-Request") == "true"


class V3CommitAuthorEmailCardMixin:
    """Shared rendering for the v3 profile page's commit-email card body, so
    the create/delete/resend views below all hand back the same up-to-date
    markup after making their change.
    """

    def _card_body(self, request, form=None, card_error=""):
        return TemplateResponse(
            request,
            "v3/includes/_commit_email_card_body.html",
            {
                "commit_email_addresses": CommitAuthorEmail.claimed_by_user(
                    request.user
                ),
                "commit_email_form": form or V3CommitAuthorEmailForm(),
                "commit_email_card_error": card_error,
                # only ever called on the htmx path below, so the card's
                # no-JS fallback must be left out (see the template)
                "htmx_swap": True,
            },
        )

    def _redirect_to_profile(self, request, email="", stale=False):
        """Post/Redirect/Get back to the edit-profile page.

        With JS off there is no htmx swap to carry a failure back into the
        card, and the v3 edit template deliberately swallows Django `messages`
        (it shows per-section save state instead), so what failed has to
        survive the redirect. Only the inputs travel, never the message: the
        profile view re-validates `ce_email` to regenerate the add error, and
        `ce_alert` is a bare flag it maps to a constant. That keeps a single
        source for every message and stops a hand-crafted URL from putting
        arbitrary text in the card.
        """
        params = {"edit": "true"}
        if email:
            params["ce_email"] = email
        if stale:
            params["ce_alert"] = "1"
        return redirect(f"{reverse('profile-account')}?{urlencode(params)}")

    def _invalid_add(self, request, form):
        """Report a rejected add: htmx swaps the card back with the bound
        form, while the no-JS redirect hands the address to the profile view,
        which rebuilds the same bound form from it.
        """
        if _is_htmx(request):
            return self._card_body(request, form=form)
        return self._redirect_to_profile(
            request, email=form.data.get("commit_email", "")
        )

    def _stale_action(self, request):
        """A list-row action that no longer applies - the row was verified or
        withdrawn since the page rendered, or the request was forged past a
        hidden button. This was a bare 404, which htmx silently drops and
        which is a dead end with JS off; either way the user was told nothing.
        The action is still refused; only the reporting changed.
        """
        if _is_htmx(request):
            return self._card_body(request, card_error=COMMIT_EMAIL_STALE_ACTION_ERROR)
        return self._redirect_to_profile(request, stale=True)


class V3CommitAuthorEmailCreateView(
    LoginRequiredMixin, V3CommitAuthorEmailCardMixin, View
):
    def post(self, request, *args, **kwargs):
        form = V3CommitAuthorEmailForm(request.POST, user=request.user)
        if not form.is_valid():
            return self._invalid_add(request, form)

        commit_author_email = form.commit_author_email
        if address_already_proven_by(commit_author_email.email, request.user):
            # the account has already confirmed this address (signup, another
            # account email, or a mailing-list subscription), so mailing a
            # token would ask the user to prove the same inbox twice
            accepted = commit_author_email.accept_proven_claim(request.user)
        else:
            accepted = commit_author_email.ask_to_claim(request)

        if accepted is None:
            # the row was verified or claimed by someone else between the
            # form's (unlocked) validation and the locked re-check
            form.add_error(
                "commit_email", "This email address can no longer be claimed."
            )
            return self._invalid_add(request, form)

        if _is_htmx(request):
            return self._card_body(request)
        return self._redirect_to_profile(request)


class V3CommitAuthorEmailWithdrawView(
    LoginRequiredMixin, V3CommitAuthorEmailCardMixin, View
):
    """Withdraw a pending (unverified) claim. The CommitAuthorEmail row
    belongs to the commit importer and is never deleted; only the claim
    fields on the row are cleared (see withdraw_claim). Verified claims
    are historical record-keeping for contribution stats, so they are
    refused even if the request is forged past a hidden button, as are
    emails with no open ask.
    """

    def post(self, request, *args, **kwargs):
        # locked read so the guards can't race a concurrent verify: whoever
        # locks first wins and the loser re-evaluates (verified -> refused)
        with transaction.atomic():
            commit_author_email = (
                CommitAuthorEmail.objects.select_for_update()
                .filter(
                    pk=kwargs["pk"],
                    claimed_by=request.user,
                    claim_verified=False,
                    claim_hash__isnull=False,
                )
                .first()
            )
            if commit_author_email is not None:
                commit_author_email.withdraw_claim()

        if commit_author_email is None:
            return self._stale_action(request)
        if _is_htmx(request):
            return self._card_body(request)
        return self._redirect_to_profile(request)


class V3CommitAuthorEmailResendView(
    LoginRequiredMixin, V3CommitAuthorEmailCardMixin, View
):
    def post(self, request, *args, **kwargs):
        # no outer transaction: ask_to_claim re-checks its preconditions
        # under its own row lock, and the verification email must be
        # enqueued after that lock commits, not while it is held
        commit_author_email = CommitAuthorEmail.objects.filter(
            pk=kwargs["pk"],
            claimed_by=request.user,
            claim_verified=False,
            claim_hash__isnull=False,
        ).first()
        if commit_author_email is None:
            return self._stale_action(request)
        commit_author_email.ask_to_claim(request)

        if _is_htmx(request):
            return self._card_body(request)
        return self._redirect_to_profile(request)
