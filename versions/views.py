from django.db.models.query import QuerySet
import structlog
from itertools import groupby
from operator import attrgetter

from django.db.models import Q, Count
from django.views.generic import DetailView, TemplateView, ListView
from django.views.generic.edit import FormMixin
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from core.models import RenderedContent
from libraries.constants import LATEST_RELEASE_URL_PATH_STR
from libraries.forms import VersionSelectionForm
from libraries.mixins import VersionAlertMixin
from libraries.models import Commit, CommitAuthor
from libraries.utils import (
    set_selected_boost_version,
    determine_selected_boost_version,
    library_doc_latest_transform,
)
from versions.models import Review, Version


logger = structlog.get_logger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class VersionDetail(FormMixin, VersionAlertMixin, DetailView):
    """Web display of list of Versions"""

    form_class = VersionSelectionForm
    model = Version
    queryset = Version.objects.active().defer("data")
    template_name = "versions/detail.html"

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
        obj = self.get_object()
        context["heading"] = self.get_version_heading(
            obj, context["current_release"] == obj
        )
        context["release_notes"] = self.get_release_notes(obj)
        context["top_contributors_release"] = self.get_top_contributors_release(obj)

        context["documentation_url"] = obj.documentation_url
        if context["version_str"] == LATEST_RELEASE_URL_PATH_STR:
            context["documentation_url"] = library_doc_latest_transform(
                obj.documentation_url
            )
            context["version_alert"] = False
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
        version_slug = self.request.POST.get("version")
        if version_slug == LATEST_RELEASE_URL_PATH_STR:
            response = redirect("releases-most-recent")
            set_selected_boost_version(LATEST_RELEASE_URL_PATH_STR, response)
            return response
        elif form.is_valid():
            version = form.cleaned_data["version"]
            response = redirect(
                "release-detail",
                slug=version.slug,
            )
            set_selected_boost_version(version.slug, response)
            return response
        else:
            logger.info("version_detail_invalid_version")
        return super().get(request)

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)

        # if 'release' clear the version values, e.g. from version_alert
        if self.kwargs.get("slug") == LATEST_RELEASE_URL_PATH_STR:
            response = redirect("releases-most-recent")
            set_selected_boost_version(LATEST_RELEASE_URL_PATH_STR, response)
            return response

        version = determine_selected_boost_version(
            self.kwargs.get("slug"), self.request
        )
        if version != self.kwargs.get("slug"):
            response = redirect(
                "release-detail",
                slug=version,
            )

        return response

    def get_object(self, queryset=None):
        """Return the object that the view is displaying"""
        if self.request.POST:
            version_slug = self.request.POST.get("version")
        else:
            version_slug = self.kwargs.get("slug", LATEST_RELEASE_URL_PATH_STR)

        if version_slug == LATEST_RELEASE_URL_PATH_STR:
            return Version.objects.most_recent()

        return get_object_or_404(Version, slug=version_slug)


class InProgressReleaseNotesView(TemplateView):
    template_name = "versions/in_progress_release_notes.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["release_notes"] = self.get_in_progress_release_notes()
        return context

    def get_in_progress_release_notes(self):
        try:
            rendered_content = RenderedContent.objects.get(
                cache_key=settings.RELEASE_NOTES_IN_PROGRESS_CACHE_KEY
            )
            return rendered_content.content_html
        except RenderedContent.DoesNotExist:
            return


class PastReviewListView(ListView):
    model = Review
    template_name = "review/past_reviews.html"

    def get_queryset(self) -> QuerySet[Review]:
        qs = super().get_queryset()
        return qs.filter(results__isnull=False).distinct()


class ScheduledReviewListView(ListView):
    model = Review
    template_name = "review/upcoming_reviews.html"

    def get_queryset(self) -> QuerySet[Review]:
        qs = super().get_queryset()
        return qs.exclude(results__isnull=False).distinct()
