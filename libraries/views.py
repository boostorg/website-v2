import datetime
from itertools import chain

import structlog
from django.contrib import messages
from django.db.models import F, Count
from django.db.models.functions import Lower
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
from .models import (
    Category,
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
)
from .constants import SELECTED_BOOST_VERSION_COOKIE_NAME

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
        elif version == "latest":
            response.delete_cookie(SELECTED_BOOST_VERSION_COOKIE_NAME)
        else:
            logger.warning(f"Attempted to set invalid version slug: {version}")

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.GET.copy()

        # If the user has selected a version, fetch it from the cookies.
        selected_boost_version = self.get_selected_boost_version()
        if selected_boost_version != params.get("version", None):
            params["version"] = selected_boost_version

        # default to the most recent version
        if "version" not in params or params["version"] == "latest":
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

        if "version" not in self.request.GET or self.request.GET["version"] == "latest":
            context["version"] = Version.objects.most_recent()
        else:
            context["version"] = Version.objects.get(slug=self.request.GET["version"])

        context["categories"] = self.get_categories(context["version"])
        context["versions"] = self.get_versions()
        context["library_list"] = self.get_queryset()
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
        return versions

    def dispatch(self, request, *args, **kwargs):
        """Set the selected version in the cookies."""
        response = super().dispatch(request, *args, **kwargs)
        query_params = build_view_query_params_from_request(request)
        # check if one was set, if not then default to cookie value for latest
        # (practically speaking, that means no cookie)
        self.set_selected_boost_version(response, query_params.get("version", "latest"))

        view = determine_view_from_library_request(request)
        # The following conditional practically only applies on "/libraries/", at
        # which point the redirection will be determined by prioritised view
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
        exclude_maintainer_ids = [
            getattr(x.commitauthor, "id")
            for x in context["maintainers"]
            if x.commitauthor
        ]
        context["top_contributors_release"] = self.get_top_contributors(
            version=context["version"],
            exclude=exclude_maintainer_ids,
        )
        exclude_top_contributor_ids = [
            x.id for x in context["top_contributors_release"]
        ]
        context["top_contributors_overall"] = self.get_top_contributors(
            exclude=exclude_maintainer_ids + exclude_top_contributor_ids
        )
        # Since we need to execute these queries separately anyway, just concatenate
        # their results instead of making a new query
        all_contributors = []
        for x in chain(
            context["top_contributors_release"], context["top_contributors_overall"]
        ):
            all_contributors.append(
                {
                    "name": x.name,
                }
            )
        for x in context["maintainers"]:
            all_contributors.append(
                {
                    "name": x.get_full_name(),
                }
            )

        all_contributors.sort(key=lambda x: x["name"].lower())
        context["all_contributors"] = all_contributors

        # Populate the commit graphs
        context["commit_data_by_release"] = self.get_commit_data_by_release()

        # Populate the library description
        client = GithubAPIClient(repo_slug=self.object.github_repo)
        context["description"] = self.object.get_description(
            client, tag=context["version"].name
        )

        return context

    def get_commit_data_by_release(self):
        qs = (
            LibraryVersion.objects.filter(library=self.object)
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
        """Get the maintainers for the current LibraryVersion.

        Also patches the CommitAuthor onto the user, if a matching email exists.
        """
        obj = self.get_object()
        library_version = LibraryVersion.objects.get(library=obj, version=version)
        qs = list(library_version.maintainers.all())
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
                user.commitauthor = None
        return qs

    def get_top_contributors(self, version=None, exclude=None):
        if version:
            library_version = LibraryVersion.objects.get(
                library=self.object, version=version
            )
            qs = CommitAuthor.objects.filter(commit__library_version=library_version)
        else:
            qs = CommitAuthor.objects.filter(
                commit__library_version__library=self.object
            )
        if exclude:
            qs = qs.exclude(id__in=exclude)
        qs = qs.annotate(count=Count("commit")).order_by("-count")
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
