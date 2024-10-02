import structlog

from django.db.models import Q, Count
from django.views.generic import DetailView
from django.views.generic.edit import FormMixin
from django.shortcuts import redirect
from django.contrib import messages
from itertools import groupby
from operator import attrgetter

from core.models import RenderedContent
from libraries.forms import VersionSelectionForm
from libraries.models import Commit, CommitAuthor
from versions.models import Version
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

SELECTED_BOOST_VERSION_COOKIE_NAME = "boost_version"

logger = structlog.get_logger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class VersionDetail(FormMixin, DetailView):
    """Web display of list of Versions"""

    form_class = VersionSelectionForm
    model = Version
    queryset = Version.objects.active().defer("data")
    template_name = "versions/detail.html"

    def get_selected_boost_version(self):
        """Returns the selected Boost version"""
        version_slug = self.request.COOKIES.get(
            SELECTED_BOOST_VERSION_COOKIE_NAME, None
        )
        if version_slug:
            try:
                version = Version.objects.get(slug=version_slug)
                return version
            except Version.DoesNotExist:
                logger.warning(f"Invalid version slug in cookies: {version_slug}")
                return None
        return None

    def set_selected_boost_version(self, response, version_slug):
        """Sets the selected Boost version"""
        try:
            Version.objects.get(slug=version_slug)
            response.set_cookie(SELECTED_BOOST_VERSION_COOKIE_NAME, version_slug)
        except Version.DoesNotExist:
            logger.warning(f"Attempted to set invalid version slug: {version_slug}")
            messages.error(self.request, "Invalid version selected.")

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        obj = self.get_object()

        # Handle the case where no data has been uploaded
        if not obj:
            messages.add_message(
                self.request,
                messages.WARNING,
                "No data has been imported yet. Please check back later.",
            )
            context["versions"] = None
            context["downloads"] = None
            context["current_release"] = None
            context["is_current_release"] = False
            return context

        context["versions"] = Version.objects.version_dropdown_strict()
        downloads = obj.downloads.all().order_by("operating_system")
        context["downloads"] = {
            k: list(v)
            for k, v in groupby(downloads, key=attrgetter("operating_system"))
        }
        current_release = Version.objects.most_recent()
        context["current_release"] = current_release
        obj = self.get_object()
        is_current_release = bool(current_release == obj)
        context["is_current_release"] = is_current_release

        context["heading"] = self.get_version_heading(obj, is_current_release)
        context["release_notes"] = self.get_release_notes(obj)
        context["top_contributors_release"] = self.get_top_contributors_release(obj)

        return context

    def get_top_contributors_release(self, version: Version):
        version_commits = Commit.objects.filter(library_version__version=version)
        qs = (
            CommitAuthor.objects.annotate(
                count=Count("commit", filter=Q(commit__in=version_commits)),
            )
            .filter(count__gte=1)
            .order_by("-count")
        )
        return qs

    def get_release_notes(self, obj):
        try:
            rendered_content = RenderedContent.objects.get(
                cache_key=obj.release_notes_cache_key
            )
            return rendered_content.content_html
        except RenderedContent.DoesNotExist:
            return

    def get_version_heading(self, obj, is_current_release):
        """Returns the heading of the versions template"""
        if is_current_release:
            return "Newest Release"
        elif all([not is_current_release, obj.beta]):
            return "Beta Release"
        elif all([obj.full_release, not is_current_release]):
            return "Prior Release"
        else:
            return "Development Branch"

    def post(self, request, *args, **kwargs):
        """User has submitted a form and will be redirected to the right record."""
        form = self.get_form()
        if form.is_valid():
            version = form.cleaned_data["version"]
            response = redirect(
                "release-detail",
                slug=version.slug,
            )
            self.set_selected_boost_version(response, version.slug)
            return response
        else:
            logger.info("version_detail_invalid_version")
        return super().get(request)

    def dispatch(self, request, *args, **kwargs):
        """Set the version if it is not already set."""

        version_in_url = self.kwargs.get("slug", False)

        if version_in_url:
            response = super().dispatch(request, *args, **kwargs)
            self.set_selected_boost_version(response, version_in_url)
            return response
        else:
            redirect_to_version = self.get_selected_boost_version()
            if redirect_to_version:
                return redirect(
                    "release-detail", slug=redirect_to_version.slug, permanent=False
                )

        return super().dispatch(request, *args, **kwargs)


class VersionCurrentReleaseDetail(VersionDetail):
    """Web display of list of Versions"""

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        context["is_current_release"] = True
        return context

    def get_object(self):
        return Version.objects.most_recent()
