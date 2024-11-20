from django.contrib import admin

from django.db.models.query import QuerySet
from django.http import HttpRequest, HttpResponseRedirect
from django.urls import path

from . import models
from .tasks import (
    import_versions,
    import_most_recent_beta_release,
    import_development_versions,
)


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
        ]
        return my_urls + urls

    def import_new_releases(self, request):
        import_versions.delay(new_versions_only=True)
        import_most_recent_beta_release.delay(delete_old=True)
        # Import the master and develop branches
        import_development_versions.delay()
        self.message_user(
            request,
            """
            New releases are being imported. If you don't see any new releases,
            please refresh this page or check the logs.
        """,
        )
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
