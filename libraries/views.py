import datetime
from types import SimpleNamespace

import structlog
from django.contrib import messages
from django.db.models import F, Count, Exists, OuterRef, Prefetch
from django.db.models.functions import Lower
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import DetailView, ListView
from django.views.generic.edit import FormMixin
from django import urls
from django.http import HttpResponseRedirect

from core.githubhelper import GithubAPIClient
from versions.models import Version

from .constants import README_MISSING
from .forms import VersionSelectionForm
from .mixins import VersionAlertMixin
from .models import (
    Category,
    Commit,
    CommitAuthor,
    CommitAuthorEmail,
    Library,
    LibraryVersion,
)
from .utils import (
    redirect_to_view_with_params,
    get_view_from_cookie,
    set_view_in_cookie,
    get_prioritized_library_view,
    build_view_query_params_from_request,
    build_route_name_for_view,
    determine_view_from_library_request,
    determine_selected_boost_version,
    set_selected_boost_version,
    get_documentation_url,
)
from .constants import LATEST_RELEASE_URL_PATH_STR

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

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.GET.copy()

        # If the user has selected a version, fetch it from the cookies.
        selected_boost_version = (
            determine_selected_boost_version(
                self.request.GET.get("version"), self.request
            )
            or LATEST_RELEASE_URL_PATH_STR
        )
        # default to the most recent version
        if selected_boost_version == LATEST_RELEASE_URL_PATH_STR:
            # If no version is specified, show the most recent version.
            version = Version.objects.most_recent()
            if version:
                selected_boost_version = version.slug
            else:
                # Add a message that no data has been imported
                messages.add_message(
                    self.request,
                    messages.WARNING,
                    "No data has been imported yet. Please check back later.",
                )
                return Library.objects.none()

        queryset = queryset.filter(
            library_version__version__slug=selected_boost_version
        )

        # avoid attempting to look up libraries with blank categories
        if params.get("category"):
            queryset = queryset.filter(categories__slug=params.get("category"))

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Handle the case where data hasn't been imported yet
        version = Version.objects.most_recent()
        version_str = determine_selected_boost_version(
            self.request.GET.get("version"), self.request
        )
        if not version_str:
            version_str = LATEST_RELEASE_URL_PATH_STR
        if not version:
            context.update(
                {
                    "category": None,
                    "version": None,
                    "version_str": version_str,
                    "categories": Category.objects.none(),
                    "versions": Version.objects.none(),
                    "library_version_list": LibraryVersion.objects.none(),
                }
            )
            return context

        if self.request.GET.get("category"):
            context["category"] = Category.objects.get(
                slug=self.request.GET["category"]
            )
        context["categories"] = self.get_categories(context["version"])
        context["versions"] = self.get_versions()
        context["version_str"] = version_str
        # todo: add tests for sort order, consider refactor to queryset use
        library_versions_qs = (
            LibraryVersion.objects.filter(
                version__slug=version_str
                if version_str != LATEST_RELEASE_URL_PATH_STR
                else version.slug
            )
            .prefetch_related("authors", "library", "library__categories")
            .order_by("library__name")
        )
        if self.request.GET.get("category"):
            library_versions_qs = library_versions_qs.filter(
                library__categories__slug=self.request.GET.get("category")
            )
        context["library_version_list"] = library_versions_qs
        context["url_params"] = build_view_query_params_from_request(self.request)

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
        versions.prefetch_related("library_version")
        return versions

    def dispatch(self, request, *args, **kwargs):
        """Set the selected version in the cookies."""
        response = super().dispatch(request, *args, **kwargs)
        query_params = build_view_query_params_from_request(request)
        set_selected_boost_version(
            query_params.get("version", LATEST_RELEASE_URL_PATH_STR), response
        )
        # The following conditional practically only applies on "/libraries/", at
        # which point the redirection will be determined by prioritised view
        view = determine_view_from_library_request(request)
        if not view:
            view = get_prioritized_library_view(request)
            set_view_in_cookie(response, build_route_name_for_view(view))
            return redirect_to_view_with_params(view, kwargs, query_params)

        if view != get_view_from_cookie(request):
            set_view_in_cookie(response, build_route_name_for_view(view))

        return response


class LibraryListMini(LibraryList):
    """Flat list version of LibraryList"""

    template_name = "libraries/flat_list.html"


class LibraryListByCategory(LibraryList):
    """List all Boost libraries sorted by Category."""

    template_name = "libraries/category_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["library_versions_by_category"] = self.get_results_by_category(
            version=context.get("version")
        )
        return context

    def get_results_by_category(self, version: Version | None):
        # Define filter kwargs based on whether version is provided
        version_filter = {"version": version} if version else {}
        category_filter = (
            {"libraries__library_version__version": version} if version else {}
        )
        library_versions_qs = LibraryVersion.objects.filter(**version_filter)

        libraries_prefetch = Prefetch(
            "libraries",
            queryset=Library.objects.order_by("name").prefetch_related(
                Prefetch(
                    "library_version",
                    queryset=library_versions_qs,
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
class LibraryDetail(FormMixin, VersionAlertMixin, DetailView):
    """Display a single Library in insolation"""

    form_class = VersionSelectionForm
    model = Library
    template_name = "libraries/detail.html"
    redirect_to_docs = False

    def get_context_data(self, **kwargs):
        """Set the form action to the main libraries page"""
        context = super().get_context_data(**kwargs)
        # Get fields related to Boost versions
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
        context["LATEST_RELEASE_URL_PATH_NAME"] = LATEST_RELEASE_URL_PATH_STR
        # Get general data and version-sensitive data
        library_version = LibraryVersion.objects.get(
            library=self.get_object(), version=context["version"]
        )
        context["library_version"] = library_version
        context["documentation_url"] = get_documentation_url(
            library_version, context["version_str"] == LATEST_RELEASE_URL_PATH_STR
        )
        context["github_url"] = self.get_github_url(context["version"])
        context["authors"] = self.get_related(library_version, "authors")
        context["maintainers"] = self.get_related(
            library_version,
            "maintainers",
            exclude_ids=[x.id for x in context["authors"]],
        )
        context["author_tag"] = self.get_author_tag()
        exclude_maintainer_ids = [
            x.commitauthor.id
            for x in context["maintainers"]
            if getattr(x.commitauthor, "id", None)
        ]
        exclude_author_ids = [
            x.commitauthor.id
            for x in context["authors"]
            if getattr(x.commitauthor, "id", None)
        ]
        top_contributors_release = self.get_top_contributors(
            version=context["version"],
            exclude=exclude_maintainer_ids + exclude_author_ids,
        )
        context["top_contributors_release_new"] = [
            x for x in top_contributors_release if x.is_new
        ]
        context["top_contributors_release_old"] = [
            x for x in top_contributors_release if not x.is_new
        ]
        exclude_top_contributor_ids = [x.id for x in top_contributors_release]
        context["previous_contributors"] = self.get_previous_contributors(
            context["version"],
            exclude=exclude_maintainer_ids
            + exclude_top_contributor_ids
            + exclude_author_ids,
        )
        # Populate the commit graphs
        context["commit_data_by_release"] = self.get_commit_data_by_release()

        # Populate the library description
        client = GithubAPIClient(repo_slug=self.object.github_repo)
        context["description"] = (
            self.object.get_description(client, tag=context["version"].name)
            or README_MISSING
        )

        return context

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

    def get_object(self):
        """Get the current library object from the slug in the URL.
        If present, use the version_slug to get the right LibraryVersion of the library.
        Otherwise, default to the most recent version."""
        slug = self.kwargs.get("slug")
        version = self.get_version()

        if not LibraryVersion.objects.filter(
            version=version, library__slug__iexact=slug
        ).exists():
            raise Http404("No library found matching the query")

        try:
            obj = self.get_queryset().get(slug__iexact=slug)
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

    def get_current_library_version(self, version):
        """Return the library-version for the latest version of Boost"""
        # Avoid raising an error if the library has been removed from the latest version
        return LibraryVersion.objects.filter(
            library=self.object, version=version
        ).first()

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

    def get_related(self, library_version, relation="maintainers", exclude_ids=None):
        """Get the maintainers|authors for the current LibraryVersion.

        Also patches the CommitAuthor onto the user, if a matching email exists.
        """
        if relation == "maintainers":
            qs = library_version.maintainers.all()
        elif relation == "authors":
            qs = library_version.authors.all()
        else:
            raise ValueError("relation must be maintainers or authors.")
        if exclude_ids:
            qs = qs.exclude(id__in=exclude_ids)
        qs = list(qs)
        commit_authors = {
            author_email.email: author_email
            for author_email in CommitAuthorEmail.objects.annotate(
                email_lower=Lower("email")
            )
            .filter(email_lower__in=[x.email.lower() for x in qs])
            .select_related("author")
        }
        for user in qs:
            if author_email := commit_authors.get(user.email.lower(), None):
                user.commitauthor = author_email.author
            else:
                user.commitauthor = SimpleNamespace(
                    github_profile_url="",
                    avatar_url="",
                )
        return qs

    def get_top_contributors(self, version=None, exclude=None):
        if version:
            library_version = LibraryVersion.objects.get(
                library=self.object, version=version
            )
            prev_versions = Version.objects.minor_versions().filter(
                version_array__lt=version.cleaned_version_parts_int
            )
            qs = CommitAuthor.objects.filter(
                commit__library_version=library_version
            ).annotate(
                is_new=~Exists(
                    Commit.objects.filter(
                        author_id=OuterRef("id"),
                        library_version__in=LibraryVersion.objects.filter(
                            version__in=prev_versions, library=self.object
                        ),
                    )
                )
            )
        else:
            qs = CommitAuthor.objects.filter(
                commit__library_version__library=self.object
            )
        if exclude:
            qs = qs.exclude(id__in=exclude)
        qs = qs.annotate(count=Count("commit")).order_by("-count")
        return qs

    def get_previous_contributors(self, version, exclude=None):
        library_versions = LibraryVersion.objects.filter(
            library=self.object,
            version__in=Version.objects.minor_versions().filter(
                version_array__lt=version.cleaned_version_parts_int
            ),
        )
        qs = (
            CommitAuthor.objects.filter(commit__library_version__in=library_versions)
            .annotate(count=Count("commit"))
            .order_by("-count")
        )
        if exclude:
            qs = qs.exclude(id__in=exclude)
        return qs

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
            return redirect(
                get_documentation_url(
                    LibraryVersion.objects.get(
                        library__slug=self.kwargs.get("slug"),
                        version=self.get_version(),
                    ),
                    latest=True,
                )
            )
        response = super().dispatch(request, *args, **kwargs)
        set_selected_boost_version(
            kwargs.get("version_slug", LATEST_RELEASE_URL_PATH_STR), response
        )
        return response

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
            return redirect(request.get_full_path())
        return super().get(request)

    def render_to_response(self, context):
        if self.object.slug != self.kwargs["slug"]:
            # redirect to canonical case
            try:
                url = urls.reverse(
                    "library-detail-by-version",
                    kwargs={
                        "slug": self.object.slug,
                        "version_slug": self.kwargs["version_slug"],
                    },
                )
            except KeyError:
                url = urls.reverse(
                    "library-detail",
                    kwargs={
                        "slug": self.object.slug,
                    },
                )
            return HttpResponseRedirect(url)
        else:
            return super().render_to_response(context)
