from django.contrib import admin

from django.db.models.query import QuerySet
from django.http import HttpRequest, HttpResponseRedirect
from django.urls import path

from libraries.tasks import release_tasks, import_new_versions_tasks

from . import models


class VersionFileInline(admin.StackedInline):
    model = models.VersionFile
    autocomplete_fields = ("version",)
    verbose_name = "VersionFile"
    verbose_name_plural = "VersionFiles"
    extra = 0


@admin.register(models.Version)
class VersionAdmin(admin.ModelAdmin):
    list_display = ["name", "release_date", "active", "full_release", "beta"]
    list_filter = ["active", "full_release", "beta"]
    ordering = ["-release_date", "-name"]
    search_fields = ["name", "description"]
    date_hierarchy = "release_date"
    inlines = [VersionFileInline]
    change_list_template = "admin/version_change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path(
                "new_versions/",
                self.admin_site.admin_view(self.import_new_releases),
                name="import_new_releases",
            ),
            path(
                "release_tasks/",
                self.admin_site.admin_view(self.release_tasks),
                name="release_tasks",
            ),
        ]
        return my_urls + urls

    def release_tasks(self, request):
        release_tasks.delay(
            base_uri=f"https://{request.get_host()}",
            user_id=request.user.id,
            generate_report=True,
        )
        self.message_user(
            request,
            "release_tasks has started, you will receive an email when the task finishes.",  # noqa: E501
        )
        return HttpResponseRedirect("../")

    def import_new_releases(self, request):
        import_new_versions_tasks.delay(user_id=request.user.id)
        msg = "New releases are being imported. You will receive an email when the task finishes."  # noqa: E501
        self.message_user(request, msg)
        return HttpResponseRedirect("../")


class ResultInline(admin.StackedInline):
    model = models.ReviewResult
    autocomplete_fields = ("review",)
    verbose_name = "Result"
    verbose_name_plural = "Results"
    extra = 0


@admin.register(models.Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["submission", "review_dates", "get_results"]
    search_fields = ["submission"]
    inlines = [ResultInline]

    def get_results(self, obj):
        return " | ".join(obj.results.values_list("short_description", flat=True))

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return super().get_queryset(request).prefetch_related("results")


@admin.register(models.ReviewResult)
class ReviewResultAdmin(admin.ModelAdmin):
    list_display = ["review", "short_description"]

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return super().get_queryset(request).select_related("review")


@admin.register(models.ReportConfiguration)
class ReportConfigurationAdmin(admin.ModelAdmin):
    list_display = ["version"]
    filter_horizontal = ["financial_committee_members"]
