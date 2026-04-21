from textwrap import dedent

import structlog
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models.query import QuerySet
from itertools import groupby
from operator import attrgetter

from django.db.models import Q, Count
from django.http import HttpResponse
from django.views import View
from django.views.generic import DetailView, TemplateView, ListView
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from waffle import flag_is_active

from core.mixins import V3Mixin
from core.models import RenderedContent
from libraries.constants import LATEST_RELEASE_URL_PATH_STR
from libraries.mixins import VersionAlertMixin, BoostVersionMixin
from libraries.models import Commit, CommitAuthor, ReleaseReport
from libraries.tasks import generate_release_report
from libraries.utils import (
    set_selected_boost_version,
    determine_selected_boost_version,
    library_doc_latest_transform,
)
from versions.exceptions import BoostImportedDataException
from versions.models import Review, Version

logger = structlog.get_logger()


@method_decorator(csrf_exempt, name="dispatch")
class VersionDetail(V3Mixin, BoostVersionMixin, VersionAlertMixin, DetailView):
    """Web display of list of Versions"""

    model = Version
    template_name = "versions/detail.html"
    v3_template_name = "v3/release_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        # .get_object() is called on /releases, with no version pk nor existing context
        obj = context.get("selected_version") or self.get_object()

        # Handle the case where no data has been uploaded
        if not obj:
            messages.add_message(
                self.request,
                messages.WARNING,
                "No data has been imported yet. Please check back later.",
            )
            context["versions"] = None
            context["downloads"] = None
            context["selected_version"] = None
            context["is_current_release"] = False
            return context

        downloads = obj.downloads.all().order_by("operating_system", "display_name")
        for dl in downloads:
            dl.operating_system = dl.operating_system.replace("Bin", "Binary")

        context["downloads"] = {
            k: list(v)
            for k, v in groupby(downloads, key=attrgetter("operating_system"))
        }
        context["heading"] = self.get_version_heading(
            obj, context["current_version"] == obj
        )
        context["release_notes"] = self.get_release_notes(obj)
        context["top_contributors_release"] = self.get_top_contributors_release(obj)

        context["documentation_url"] = obj.documentation_url
        report_file_info = self.get_release_report_info()
        if report_file_info:
            context["release_report_file_name"] = report_file_info["file_name"]
            context["release_report_url"] = report_file_info["file_path"]
        try:
            context["deps"] = self.get_library_version_dependencies(obj)
        except BoostImportedDataException:
            logger.warning("Library version dependencies not set, need importing.")
            context["deps"] = None
            context["dependencies_not_calculated"] = True
        if context["version_str"] == LATEST_RELEASE_URL_PATH_STR:
            context["documentation_url"] = library_doc_latest_transform(
                obj.documentation_url
            )
            context["version_alert"] = False
        return context

    def get_release_report_info(self) -> dict | None:
        try:
            if report := ReleaseReport.objects.get(
                report_configuration__version=self.object.name, published=True
            ):
                return {
                    "file_name": report.file.name.replace(ReleaseReport.upload_dir, ""),
                    "file_path": report.get_media_file(),
                }
        except ReleaseReport.DoesNotExist:
            return {}

    def get_library_version_dependencies(self, version: Version):
        diffs = version.get_dependency_diffs()
        added = [len(x["added"]) for x in diffs.values() if x["added"]]
        removed = [len(x["removed"]) for x in diffs.values() if x["removed"]]
        return {
            "added": sum(added),
            "removed": sum(removed),
            "increased_dep_lib_count": len(added),
            "decreased_dep_lib_count": len(removed),
        }

    def get_top_contributors_release(self, version: Version):
        version_commits = Commit.objects.filter(library_version__version=version)
        qs = (
            CommitAuthor.humans.annotate(
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

    def get_v3_context_data(self, **kwargs):
        obj = self.object
        ctx = {}
        ctx["hero_title"] = f"Latest release ({obj.display_name})"
        ctx["whats_new_heading"] = f"What's new in {obj.display_name}"
        ctx["whats_new_items"] = [
            {
                "title": "Asio: Major Executor & Reactor Overhaul",
                "description": "New inline executor model, improved cancellation, expanded epoll configuration, and numerous correctness + performance fixes.",
            },
            {
                "title": "Container: Complete deque Rebuild",
                "description": "A modern, faster, drastically smaller deque implementation that simplifies future optimizations and resolves multiple long-standing issues.",
            },
            {
                "title": "Redis: Major Redesign of Cancellation & Connection Behavior",
                "description": "True per-operation cancellation, deprecated old mechanisms, smarter health checking, and guaranteed Valkey compatibility.",
            },
            {
                "title": "Math: Brand-New Reverse-Mode Automatic Differentiation Library",
                "description": "Adds full AD capabilities to Boost.Math, enabling modern ML/scientific workflows directly within Boost.",
            },
            {
                "title": "Geometry: New is_valid for Polyhedral Surfaces + Performance Fixes",
                "description": "A major algorithm addition, improved conversion support, and fixes to reduce compile times and avoid stack overflows.",
            },
        ]
        ctx["release_notes"] = {
            "title": f"Release notes version {obj.display_name}",
            "html": dedent(
                """\
                <h2>Dependencies</h2>
                <p>There was 1 dependency added (in 1 library) and 16 dependencies removed (in 10 libraries) this release.</p>
                <ul>
                <li><a href="https://www.boost.org">Official Site</a></li>
                <li><a href="https://www.boost.org/doc/libs/master/">Documentation (master branch)</a></li>
                <li><a href="https://www.boost.org">Autobahn|Testsuite WebSocket Results</a></li>
                </ul>
                <h2>New Libraries</h2>
                <p><strong>OpenMethod:</strong></p>
                <ul>
                <li>Open-(multi-)methods in C++17 and above, from Jean-Louis Leroy.</li>
                </ul>
                <h2>Updated Libraries</h2>
                <p><strong>Asio</strong></p>
                <ul>
                <li>Added the execution::inline_exception_handling property to describe what exception handling guarantees are made when execution occurs inline.</li>
                <li>Added inline_executor, which always executes the submitted function inline.</li>
                <li>Changed the default candidate executor for associated_executor from system_executor to inline_executor.</li>
                <li>Added the inline_or_executor&lt;&gt; adapter and inline_or() helper, which will execute inline if possible and otherwise delegate to another executor.</li>
                <li>Added overloads of dispatch, post and defer that take a function object to be run on the target executor, and deliver the result to the completion handler.</li>
                <li>Added the redirect_disposition completion token adapter, as a generic counterpart for redirect_error.</li>
                <li>Annotated deprecated items with the [[deprecated]] attribute.</li>
                <li>Added a new configuration parameter "reactor" / "reset_edge_on_partial_read", which determines whether a partial read consumes the edge when using epoll.</li>
                <li>Added the missing preprocessor check for BOOST_ASIO_DISABLE_TIMERFD.</li>
                <li>Implemented a compile-time feature detection mechanism for io_uring.</li>
                </ul>"""
            ),
        }
        top_contributors = self.get_top_contributors_release(obj)
        if top_contributors:
            ctx["v3_contributors"] = [
                {
                    "name": author.display_name,
                    "avatar_url": author.avatar_url or "",
                    "profile_url": author.github_profile_url or "",
                    "role": "Contributor",
                }
                for author in top_contributors
            ]
        return ctx

    def dispatch(self, request, *args, **kwargs):
        version_slug = self.kwargs.get("version_slug")

        if self.v3_template_name and flag_is_active(request, "v3"):
            self._v3_active = True
            if not version_slug:
                return redirect(
                    "release-detail",
                    version_slug=LATEST_RELEASE_URL_PATH_STR,
                )
            self.object = self.get_object()
            self.set_extra_context(request)
            context = self.get_context_data()
            context.update(self.get_v3_context_data())
            response = self.render_to_response(context)
            set_selected_boost_version(version_slug, response)
            return response

        self._v3_active = False
        response = super().dispatch(request, *args, **kwargs)
        # if set in kwargs, update the cookie
        if version_slug:
            set_selected_boost_version(version_slug, response)
        else:
            version_slug = (
                determine_selected_boost_version(version_slug, self.request)
                or LATEST_RELEASE_URL_PATH_STR
            )
            response = redirect(
                "release-detail",
                version_slug=version_slug,
            )
        return response

    def get_object(self, queryset=None):
        """Return the object that the view is displaying"""
        version_slug = self.kwargs.get("version_slug", LATEST_RELEASE_URL_PATH_STR)
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
        return (
            qs.filter(results__isnull=False)
            .distinct()
            .select_related("review_manager")
            .prefetch_related("results", "submitters")
            .order_by("id")
        )


class ScheduledReviewListView(ListView):
    model = Review
    template_name = "review/upcoming_reviews.html"

    def get_queryset(self) -> QuerySet[Review]:
        qs = super().get_queryset()
        return qs.exclude(results__isnull=False).distinct()


@method_decorator(staff_member_required, name="get")
class ReportPreviewView(BoostVersionMixin, View):
    extra_context = {}

    def get(self, request, *args, **kwargs):
        version_name = self.extra_context["selected_version"].name
        # TODO: this is a bit silly. There's probably a more elegant solution
        cache_key = f"release-report-,,,,,,,-{version_name}"
        # TODO: it might be better to show a friendly "report not yet generated"
        #  message instead of 404ing.
        content = get_object_or_404(RenderedContent, cache_key=cache_key)
        return HttpResponse(content.content_html)


@method_decorator(staff_member_required, name="get")
class ReportPreviewGenerateView(BoostVersionMixin, View):
    """
    Regenerate a report without importing all data.
    This is much faster - useful for when importing is not needed.
    """

    extra_context = {}

    def get(self, request, *args, **kwargs):
        version = self.extra_context["selected_version"]
        version_name = version.name
        cache_key = f"release-report-,,,,,,,-{version_name}"
        RenderedContent.objects.filter(cache_key=cache_key).delete()
        generate_release_report.delay(
            user_id=request.user.id,
            params={"version": version.id},
            base_uri=f"{settings.ACCOUNT_DEFAULT_HTTP_PROTOCOL}://{request.get_host()}",
        )
        messages.success(request, "Report generation queued.")
        return redirect("release-report-preview", version_slug=version_name)
