import re

import structlog
from types import SimpleNamespace

from django.db.models import Count, Exists, OuterRef
from django.db.models.functions import Lower
from django.shortcuts import get_object_or_404
from django.urls import reverse

from libraries.constants import (
    LATEST_RELEASE_URL_PATH_STR,
    MASTER_RELEASE_URL_PATH_STR,
    DEVELOP_RELEASE_URL_PATH_STR,
)
from libraries.models import (
    Commit,
    CommitAuthor,
    CommitAuthorEmail,
    Library,
    LibraryVersion,
)
from versions.models import Version

logger = structlog.get_logger()


class VersionAlertMixin:
    """Mixin to selectively add a version alert to the context"""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        url_name = self.request.resolver_match.url_name
        if url_name in {"libraries", "releases-most-recent"}:
            return context
        current_version_kwargs = self.kwargs.copy()

        if url_name == "docs-libs-page":
            alert_visible = not current_version_kwargs.get("content_path").startswith(
                LATEST_RELEASE_URL_PATH_STR
            )
            current_version_kwargs.update(
                {
                    "content_path": re.sub(
                        r"([_0-9]+|master|develop)/(\S+)",
                        rf"{LATEST_RELEASE_URL_PATH_STR}/\2",
                        current_version_kwargs.get("content_path"),
                    )
                }
            )
        else:
            current_version_kwargs.update({"version_slug": LATEST_RELEASE_URL_PATH_STR})
            alert_visible = (
                self.kwargs.get("version_slug") != LATEST_RELEASE_URL_PATH_STR
            )
        context["version_alert_url"] = reverse(url_name, kwargs=current_version_kwargs)
        context["version_alert"] = alert_visible
        return context


class BoostVersionMixin:
    def dispatch(self, request, *args, **kwargs):
        self.set_extra_context(request)
        return super().dispatch(request, *args, **kwargs)

    def set_extra_context(self, request):
        if not self.extra_context:
            self.extra_context = {}
        if not self.extra_context.get("current_version"):
            self.extra_context["current_version"] = Version.objects.most_recent()
        self.extra_context.update(
            {
                "version_str": self.kwargs.get("version_slug"),
                "LATEST_RELEASE_URL_PATH_STR": LATEST_RELEASE_URL_PATH_STR,
            }
        )
        if self.extra_context["version_str"] == LATEST_RELEASE_URL_PATH_STR:
            self.extra_context["selected_version"] = self.extra_context[
                "current_version"
            ]
        elif self.extra_context["version_str"]:
            self.extra_context["selected_version"] = get_object_or_404(
                Version, slug=self.extra_context["version_str"]
            )
        version_path_kwargs = {}
        # Only when the user uses master or develop do those versions to appear
        if self.extra_context["version_str"] in [
            MASTER_RELEASE_URL_PATH_STR,
            DEVELOP_RELEASE_URL_PATH_STR,
        ]:
            version_path_kwargs[f"allow_{self.extra_context['version_str']}"] = True
        if self.request.resolver_match.view_name == "library-detail":
            version_path_kwargs["flag_versions_without_library"] = get_object_or_404(
                Library, slug=self.kwargs.get("library_slug")
            )
        self.extra_context["versions"] = Version.objects.get_dropdown_versions(
            **version_path_kwargs
        )
        # here we hack extra_context into the request so we can access for cookie checks
        request.extra_context = self.extra_context


class ContributorMixin:
    """Mixin to gather a list of all authors, maintainers, and
    contributors without duplicates.
    Uses the current Library if on the Library detail view,
    otherwise grabs a featured library
    """

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["latest_version"] = Version.objects.most_recent()

        if hasattr(self, "object") and isinstance(self.object, Library):
            library = self.object
            try:
                library_version = LibraryVersion.objects.get(
                    library=library, version=context["selected_version"]
                )
            except LibraryVersion.DoesNotExist:
                return context
        else:
            library_version = self.get_featured_library()
            context["featured_library"] = library_version

        context["authors"] = self.get_related(library_version, "authors")
        context["maintainers"] = self.get_related(
            library_version,
            "maintainers",
            exclude_ids=[x.id for x in context["authors"]],
        )
        context["author_tag"] = self.get_author_tag(library_version)
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
            library_version=library_version,
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
            library_version,
            exclude=exclude_maintainer_ids
            + exclude_top_contributor_ids
            + exclude_author_ids,
        )
        return context

    def get_featured_library(self):
        """Returns latest LibraryVersion associated with the featured Library"""
        # If multiple are featured, pick one at random
        latest_version = Version.objects.most_recent()
        library = Library.objects.filter(featured=True).order_by("?").first()

        # If we don't have a featured library, return a random library
        if not library:
            library = (
                Library.objects.filter(library_version__version=latest_version)
                .order_by("?")
                .first()
            )
        if not library:
            return None
        libversion = LibraryVersion.objects.filter(
            library_id=library.id, version=latest_version
        ).first()

        return libversion

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
                    display_name=f"{user.display_name}",
                )
        return qs

    def get_author_tag(self, library_version):
        """Format the authors for the author meta tag in the template."""
        author_names = list(
            library_version.library.authors.values_list("display_name", flat=True)
        )
        if len(author_names) > 1:
            final_output = ", ".join(author_names[:-1]) + " and " + author_names[-1]
        else:
            final_output = author_names[0] if author_names else ""

        return final_output

    def get_top_contributors(self, library_version=None, exclude=None):
        if library_version:
            prev_versions = Version.objects.minor_versions().filter(
                version_array__lt=library_version.version.cleaned_version_parts_int
            )
            qs = CommitAuthor.objects.filter(
                commit__library_version=library_version
            ).annotate(
                is_new=~Exists(
                    Commit.objects.filter(
                        author_id=OuterRef("id"),
                        library_version__in=LibraryVersion.objects.filter(
                            version__in=prev_versions, library=library_version.library
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

    def get_previous_contributors(self, library_version, exclude=None):
        library_versions = LibraryVersion.objects.filter(
            library=library_version.library,
            version__in=Version.objects.minor_versions().filter(
                version_array__lt=library_version.version.cleaned_version_parts_int
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
