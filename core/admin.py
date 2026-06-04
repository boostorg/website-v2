from datetime import date

from django.contrib import admin
from django.urls import path
from django.shortcuts import redirect, render
from django.contrib import messages
from django.db import transaction
from django.db.models import BooleanField, Case, Value, When
from django.utils import timezone

from .models import (
    PopularSearchTerm,
    PopularSearchTermExclusion,
    RenderedContent,
    SiteSettings,
)
from .tasks import delete_all_rendered_content


@admin.register(RenderedContent)
class RenderedContentAdmin(admin.ModelAdmin):
    list_display = (
        "cache_key",
        "content_type",
        "modified",
        "latest_path_matched_indicator",
        "latest_path_match_class",
    )
    search_fields = ("cache_key",)
    readonly_fields = ("latest_path_match_class",)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "start-content-refresh/",
                self.admin_site.admin_view(self.start_content_refresh_view),
                name="core_renderedcontent_start_content_refresh",
            ),
            path(
                "delete-all/",
                self.admin_site.admin_view(self.delete_all_view),
                name="core_renderedcontent_delete_all",
            ),
        ]
        return custom_urls + urls

    def start_content_refresh_view(self, request):
        if request.method == "POST":
            settings = SiteSettings.load()
            settings.rendered_content_replacement_start = timezone.now()
            settings.save()
            messages.success(
                request,
                f"Content refresh start time set to {settings.rendered_content_replacement_start}",
            )
            return redirect("..")

        context = {
            **self.admin_site.each_context(request),
            "title": "Start Content Refresh",
        }
        return render(
            request,
            "admin/core/renderedcontent/start_content_refresh_confirmation.html",
            context,
        )

    def delete_all_view(self, request):
        if request.method == "POST":
            delete_all_rendered_content.delay()
            messages.success(
                request,
                "Mass deletion task has been queued. All rendered content "
                "records will be deleted in batches. This may take some time.",
            )
            return redirect("..")

        context = {
            **self.admin_site.each_context(request),
            "title": "Delete All Rendered Content",
        }
        return render(
            request, "admin/core/renderedcontent/delete_all_confirmation.html", context
        )

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["has_start_content_refresh"] = True
        extra_context["has_delete_all"] = True
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ("id", "wordcloud_ignore", "rendered_content_replacement_start")
    readonly_fields = ("rendered_content_replacement_start",)
    filter_horizontal = ("pinned_community_libraries",)

    def has_add_permission(self, request):
        return super().has_add_permission(request) and SiteSettings.objects.count() == 0

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PopularSearchTerm)
class PopularSearchTermAdmin(admin.ModelAdmin):
    list_display = (
        "rank",
        "label",
        "search_count",
        "on_homepage",
        "updated_at",
    )
    list_display_links = ("label",)
    search_fields = ("label",)
    ordering = ("rank",)
    actions = ("move_to_exclusions",)

    def get_urls(self):
        return [
            path(
                "refresh-from-algolia/",
                self.admin_site.admin_view(self.refresh_from_algolia_view),
                name="core_popularsearchterm_refresh",
            ),
        ] + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        extra_context = {**(extra_context or {}), "has_refresh_button": True}
        return super().changelist_view(request, extra_context=extra_context)

    def get_queryset(self, request):
        # Imported here to avoid a circular import at module load time
        # (ak.views imports from core.models).
        from ak.views import HOMEPAGE_POPULAR_TERMS_DISPLAY

        visible_ids = list(
            PopularSearchTerm.objects.visible().values_list("id", flat=True)[
                :HOMEPAGE_POPULAR_TERMS_DISPLAY
            ]
        )
        return (
            super()
            .get_queryset(request)
            .annotate(
                _on_homepage=Case(
                    When(id__in=visible_ids, then=Value(True)),
                    default=Value(False),
                    output_field=BooleanField(),
                )
            )
        )

    @admin.display(boolean=True, description="On homepage?", ordering="-_on_homepage")
    def on_homepage(self, obj):
        return obj._on_homepage

    @admin.action(description="Move selected to exclusions (homepage banlist)")
    def move_to_exclusions(self, request, queryset):
        labels = list(queryset.values_list("label", flat=True))
        if not labels:
            return
        today = date.today().isoformat()
        with transaction.atomic():
            for label in labels:
                PopularSearchTermExclusion.objects.get_or_create(
                    term=label,
                    defaults={"note": f"Excluded via admin on {today}"},
                )
            queryset.delete()
        self.message_user(
            request,
            f"Excluded {len(labels)} term(s) and removed from the homepage list: "
            f"{', '.join(labels)}",
            messages.SUCCESS,
        )

    def refresh_from_algolia_view(self, request):
        if request.method != "POST":
            return redirect("..")
        from core.tasks import refresh_popular_search_terms

        refresh_popular_search_terms.delay()
        self.message_user(
            request,
            "Refresh from Algolia queued. Reload in ~5 seconds to see updated rows.",
            messages.SUCCESS,
        )
        return redirect("..")


@admin.register(PopularSearchTermExclusion)
class PopularSearchTermExclusionAdmin(admin.ModelAdmin):
    list_display = ("term", "note")
    search_fields = ("term",)
