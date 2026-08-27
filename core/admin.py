from datetime import date

from django.contrib import admin
from django.urls import path
from django.shortcuts import redirect, render
from django.contrib import messages
from django.db import transaction
from django.db.models import BooleanField, Case, Value, When
from django.utils import timezone

from core.admin_buttons import TaskButtonAdminMixin, TaskButton

from .constants import HOMEPAGE_POPULAR_TERMS_DISPLAY
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


def get_buttons():
    from badges.tasks import backfill_achievements_task
    from badges.admin import SOURCE_CHOICES

    from pages.tasks import convert_news_entries_task, update_index_task

    from libraries.tasks import import_commits

    from users.tasks import recompute_displayed_profile_roles

    CONVERT_NEW_ENTRIES_BUTTON = TaskButton(
        name="convert_news_entries",
        label="Convert News Entries",
        task=convert_news_entries_task,
        success_message="Entries are being converted in the background.",
        busy_message="A conversion is already queued or running; not starting another one.",
        argument="slug",
        pass_actor=False,
        description=("Converts legacy Entry models into Wagtail Post Pages."),
    )

    UPDATE_INDEX_BUTTON = TaskButton(
        name="update_index",
        label="Update Index",
        task=update_index_task,
        success_message="The index is being updated in the background.",
        busy_message="An index update is already queued or running; not starting another one.",
        pass_actor=False,
        description=(
            "Update the Index in order to allow for Wagtail searching. Should be run after "
            "all pages are succesfully converted."
        ),
    )

    IMPORT_COMMITS_BUTTON = TaskButton(
        name="import_commits",
        label="Import Commits",
        task=import_commits,
        success_message="Commits are being Reimported in the background.",
        busy_message="An import is already queued or running; not starting another one.",
        pass_actor=False,
        description=(
            "Cleanly Reimports all commits to reconcile before granting achievements and badges."
        ),
        permission="libraries.delete_commit",
    )

    BACKFILL_BUTTON = TaskButton(
        name="backfill",
        label="Backfill achievements",
        task=backfill_achievements_task,
        success_message="Achievements are being backfilled in the background.",
        busy_message="A backfill is already queued or running; not starting another one.",
        argument="slug",
        choice_label="Source",
        choices=SOURCE_CHOICES,
        all_label="All sources",
        pass_actor=True,
        description=(
            "Grants the automatic achievements the sources support and this site is "
            "missing, then awards any badge that reaches its threshold. It only ever "
            "adds, so it is safe to run at any time; this is what runs itself after "
            "each release. Use Reconcile instead if an achievement needs removing."
        ),
    )

    UPDATE_DISPLAYED_ROLES_BUTTON = TaskButton(
        name="update_roles",
        label="Update Roles",
        task=recompute_displayed_profile_roles,
        success_message="Roles are being updated in the background.",
        busy_message="A role update is already queued or running; not starting another one.",
        pass_actor=False,
        description=(
            "Updates available user roles based on their contributions to boost."
        ),
    )

    return [
        CONVERT_NEW_ENTRIES_BUTTON,
        UPDATE_INDEX_BUTTON,
        IMPORT_COMMITS_BUTTON,
        BACKFILL_BUTTON,
        UPDATE_DISPLAYED_ROLES_BUTTON,
    ]


@admin.register(SiteSettings)
class SiteSettingsAdmin(TaskButtonAdminMixin, admin.ModelAdmin):
    task_buttons = get_buttons()
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
        "is_pinned",
        "on_homepage",
        "updated_at",
    )
    list_display_links = ("label",)
    list_editable = ("is_pinned",)
    list_filter = ("is_pinned",)
    search_fields = ("label",)
    ordering = ("-is_pinned", "rank")
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
                if not PopularSearchTermExclusion.objects.filter(
                    term__iexact=label
                ).exists():
                    PopularSearchTermExclusion.objects.create(
                        term=label, note=f"Excluded via admin on {today}"
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
