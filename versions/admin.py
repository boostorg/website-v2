from django.contrib import admin

from django.db.models.query import QuerySet
from django.http import HttpRequest, HttpResponseRedirect
from django.urls import path
from django.utils.html import format_html, format_html_join

from core.admin_buttons import TaskButton, TaskButtonAdminMixin
from libraries.tasks import import_new_versions_tasks

from . import models
from .models import Version
from .tasks import dispatch_whats_new, import_reviews_task


def _import_reviews_preview(_request, _value):
    """Static warning for the destructive parts of review reconciliation."""
    return {
        "title": "Import reviews from boost.org",
        "summary": (
            "This re-scrapes the published formal-review results and updates the "
            "stored reviews to match. Existing reviews with the same normalized "
            "identity are updated instead of copied."
        ),
        "rows": (
            {
                "label": "Duplicate reviews",
                "detail": (
                    "Duplicate stored reviews are merged; the duplicate rows, "
                    "their results, and achievements sourced from them are deleted."
                ),
                "warning": True,
            },
            {
                "label": "Review results",
                "detail": (
                    "Published results are created or updated for every imported "
                    "review."
                ),
                "warning": False,
            },
        ),
        "warning": (
            "Continue only if boost.org is the source you intend to reconcile "
            "against."
        ),
        "can_apply": True,
    }


IMPORT_REVIEWS_BUTTON = TaskButton(
    name="import_reviews",
    label="Import Reviews from boost.org",
    task=import_reviews_task,
    success_message="Reviews are being imported from boost.org in the background.",
    busy_message=(
        "A review import is already queued or running; not starting another one."
    ),
    permission="versions.delete_review",
    confirm=_import_reviews_preview,
    description=(
        "Re-scrapes the formal-review results published on boost.org and updates "
        "the reviews and results below, matching each against what is already "
        "stored rather than adding a near-duplicate. Duplicate reviews, their "
        "results, and achievements sourced from them may be deleted; Reviewer "
        "achievements are brought into step afterwards."
    ),
)


class VersionFileInline(admin.StackedInline):
    model = models.VersionFile
    autocomplete_fields = ("version",)
    verbose_name = "VersionFile"
    verbose_name_plural = "VersionFiles"
    extra = 0


@admin.register(models.Version)
class VersionAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "release_date",
        "active",
        "beta",
        "fully_imported",
        "full_release",
        "whats_new_approved",
    ]
    list_filter = ["active", "full_release", "beta", "whats_new_approved"]
    ordering = ["-release_date", "-name"]
    search_fields = ["name", "description"]
    date_hierarchy = "release_date"
    inlines = [VersionFileInline]
    change_list_template = "admin/version_change_list.html"
    readonly_fields = ["whats_new_items_display", "whats_new_generated_at"]
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "slug",
                    "release_date",
                    "description",
                    "active",
                    "github_url",
                    "beta",
                    "full_release",
                    "data",
                    "fully_imported",
                )
            },
        ),
        (
            "What's New",
            {
                "fields": (
                    "whats_new",
                    "whats_new_items_display",
                    "whats_new_approved",
                    "whats_new_generated_at",
                ),
                "description": (
                    "AI-generated draft summary. Edit `whats_new` (markdown bullets) "
                    "and re-save to refresh the parsed items shown below, or use the "
                    "'Regenerate What's New' action. Only bullets matching the "
                    "`- **Label** — text` pattern are surfaced on the public site."
                ),
            },
        ),
    )
    actions = ["approve_whats_new", "regenerate_whats_new"]

    @admin.display(description="Parsed items (rendered on the site)")
    def whats_new_items_display(self, obj: Version) -> str:
        items = obj.whats_new_items
        if not items:
            return "(no parseable bullets — site will not render a What's New card)"
        return format_html(
            "<ul>{}</ul>",
            format_html_join(
                "",
                "<li><strong>{}</strong> — {}</li>",
                ((item["title"], item["description"]) for item in items),
            ),
        )

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        # we want all versions here, including not fully_imported
        return Version.objects.with_partials()

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path(
                "new_versions/",
                self.admin_site.admin_view(self.import_new_releases),
                name="import_new_releases",
            ),
        ]
        return my_urls + urls

    def import_new_releases(self, request):
        import_new_versions_tasks.delay(user_id=request.user.id)
        msg = "New releases are being imported. You will receive an email when the task finishes."  # noqa: E501
        self.message_user(request, msg)
        return HttpResponseRedirect("../")

    @admin.action(description="Approve What's New (publish)")
    def approve_whats_new(self, request, queryset):
        updated = queryset.exclude(whats_new="").update(whats_new_approved=True)
        self.message_user(request, f"Approved What's New for {updated} version(s).")

    @admin.action(description="Regenerate What's New (queue task)")
    def regenerate_whats_new(self, request, queryset):
        queued = 0
        for version in queryset:
            dispatch_whats_new(version.pk)
            queued += 1
        self.message_user(request, f"Queued regeneration for {queued} version(s).")


class ResultInline(admin.StackedInline):
    model = models.ReviewResult
    autocomplete_fields = ("review",)
    verbose_name = "Result"
    verbose_name_plural = "Results"
    extra = 0


@admin.register(models.Review)
class ReviewAdmin(TaskButtonAdminMixin, admin.ModelAdmin):
    list_display = [
        "id",
        "submission",
        "review_dates",
        "get_results",
        "get_review_manager",
        "get_scraped_review_manager",
    ]
    ordering = ["-id"]
    search_fields = ["submission", "review_manager_raw", "review_manager__name"]
    inlines = [ResultInline]
    task_buttons = (IMPORT_REVIEWS_BUTTON,)

    def get_results(self, obj):
        return " | ".join(result.short_description for result in obj.results.all())

    @admin.display(description="Review manager", ordering="review_manager__name")
    def get_review_manager(self, obj):
        return obj.review_manager or ""

    @admin.display(description="Scraped review manager", ordering="review_manager_raw")
    def get_scraped_review_manager(self, obj):
        return obj.review_manager_raw

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return (
            super()
            .get_queryset(request)
            .select_related("review_manager")
            .prefetch_related("results")
        )


@admin.register(models.ReviewResult)
class ReviewResultAdmin(admin.ModelAdmin):
    list_display = ["review", "short_description"]

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return super().get_queryset(request).select_related("review")


@admin.register(models.ReportConfiguration)
class ReportConfigurationAdmin(admin.ModelAdmin):
    list_display = ["version"]
    filter_horizontal = ["financial_committee_members"]
