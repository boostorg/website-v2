from datetime import date

from django.contrib import admin
from django.urls import path
from django.utils.html import format_html
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
    WysiwygImage,
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


def _synchronize_commit_author_preview(_request, _value):
    """Static warning for the destructive part of author synchronization."""
    return {
        "title": "Synchronize commit authors and members",
        "summary": (
            "This binds commit authors to the members who wrote the commits, so "
            "that commit and documentation achievements can be attributed. Run it "
            "after Update Commits and before Backfill achievements."
        ),
        "rows": (
            {
                "label": "Duplicate commit authors",
                "detail": (
                    "Authors sharing a GitHub profile are merged. Their commits "
                    "and email addresses move to the surviving row and the "
                    "duplicate is deleted; a review naming the deleted author as "
                    "a submitter loses that link, so import reviews afterwards."
                ),
                "warning": True,
            },
            {
                "label": "Member records",
                "detail": (
                    "Members with no GitHub username stored get one from the "
                    "matched author's profile. This writes to the member, not "
                    "only to the commit author."
                ),
                "warning": True,
            },
            {
                "label": "Author to member links",
                "detail": (
                    "Every unlinked author whose email matches a member is bound "
                    "to that member. Nothing already linked is changed."
                ),
                "warning": False,
            },
        ),
        "warning": (
            "Continue only if the commit import has finished; authors it has not "
            "created yet cannot be bound."
        ),
        "can_apply": True,
    }


def get_buttons():
    from dataclasses import replace

    from badges.admin import BACKFILL_BUTTON

    from pages.tasks import convert_news_entries_task, update_index_task

    from libraries.tasks import synchronize_commit_author_user_data, update_commits

    from users.tasks import recompute_displayed_profile_roles

    from versions.admin import IMPORT_REVIEWS_BUTTON

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
            "all pages are successfully converted."
        ),
    )

    UPDATE_COMMITS_BUTTON = TaskButton(
        name="update_commits",
        label="Update Commits",
        task=update_commits,
        success_message="Commits are being updated in the background.",
        busy_message="An update is already queued or running; not starting another one.",
        pass_actor=False,
        description=(
            "Run first, before Synchronize Commit Authors. Imports any commits "
            "the site is missing, which is what the commit and documentation "
            "achievements are counted from. It only ever adds or refreshes "
            "commits, so it is safe to run at any time; nothing is deleted."
        ),
    )

    SYNCHRONIZE_COMMIT_AUTHOR_BUTTON = TaskButton(
        name="synchronize_commit_author",
        label="Synchronize Commit Authors",
        task=synchronize_commit_author_user_data,
        success_message="Authors are being synchronized in the background.",
        busy_message="A synchronization is already queued or running; not starting another one.",
        permission="libraries.delete_commitauthor",
        pass_actor=False,
        confirm=_synchronize_commit_author_preview,
        description=(
            "Run after Update Commits and before Backfill achievements. This is "
            "what binds a commit author to the member who wrote the commits, by "
            "matching their email addresses, and every commit and documentation "
            "achievement is attributed through that link - skip it and the "
            "backfill grants almost none of them. It also merges commit authors "
            "sharing a GitHub profile, and fills in the GitHub username on the "
            "members it matches."
        ),
    )

    # Same button the versions changelist offers, including its confirmation
    # screen and permission; only the wording is checklist-specific.
    CHECKLIST_IMPORT_REVIEWS_BUTTON = replace(
        IMPORT_REVIEWS_BUTTON,
        description=(
            "Run after Synchronize Commit Authors and before Backfill "
            "achievements. Re-scrapes the formal-review results published on "
            "boost.org, which are the only source of the Reviewer achievement. "
            "It must follow the synchronize step: that step merges commit authors "
            "sharing a GitHub profile, and a review naming a merged-away author as "
            "its submitter loses that link. Nothing schedules this, so the "
            "Reviewer achievement is only as current as the last time it was run."
        ),
    )

    # Re-worded for the checklist, but the same button the badges changelist
    # offers: one definition of the task, its sources and its permissions.
    CHECKLIST_BACKFILL_BUTTON = replace(
        BACKFILL_BUTTON,
        description=(
            "Run last. Grants the automatic achievements the sources support and "
            "this site is missing, then awards any badge that reaches its "
            "threshold. It only ever adds, so it is safe to run at any time and "
            "safe to run again once the earlier steps have finished. Use "
            "Reconcile instead if an achievement needs removing."
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

    # Order is the checklist: commits are imported, their authors are bound to
    # members, reviews are re-scraped against those authors, and only then does
    # the backfill read all of it.
    return [
        CONVERT_NEW_ENTRIES_BUTTON,
        UPDATE_INDEX_BUTTON,
        UPDATE_COMMITS_BUTTON,
        SYNCHRONIZE_COMMIT_AUTHOR_BUTTON,
        CHECKLIST_IMPORT_REVIEWS_BUTTON,
        CHECKLIST_BACKFILL_BUTTON,
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


@admin.register(WysiwygImage)
class WysiwygImageAdmin(admin.ModelAdmin):
    """What the WYSIWYG editor has put in storage, and who put it there.

    Browse and delete only; nothing about an upload is worth editing here.
    Deleting a row deletes the file with it (see `delete_wysiwyg_image`).
    """

    list_display = (
        "preview",
        "original_filename",
        "uploader",
        "dimensions",
        "created",
    )
    # For uploader(), which touches the FK on every row.
    list_select_related = ("uploaded_by",)
    list_filter = ("created",)
    search_fields = ("original_filename", "image", "uploaded_by__email")
    date_hierarchy = "created"
    readonly_fields = (
        "full_preview",
        "image",
        "original_filename",
        "uploaded_by",
        "dimensions",
        "created",
        "modified",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description="Preview")
    def preview(self, obj):
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">'
            '<img src="{}" alt="" style="max-height:40px;max-width:80px"></a>',
            obj.image.url,
            obj.image.url,
        )

    @admin.display(description="Image")
    def full_preview(self, obj):
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">'
            '<img src="{}" alt="" style="max-height:400px;max-width:100%"></a>',
            obj.image.url,
            obj.image.url,
        )

    @admin.display(description="Uploaded by")
    def uploader(self, obj):
        return str(obj.uploaded_by) if obj.uploaded_by else "(deleted account)"

    @admin.display(description="Dimensions")
    def dimensions(self, obj):
        if not obj.width or not obj.height:
            return "—"
        return f"{obj.width} x {obj.height}"
