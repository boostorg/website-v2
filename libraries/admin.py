from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html

from .models import Category, CommitData, Issue, Library, LibraryVersion, PullRequest
from .tasks import (
    update_commit_counts,
    update_libraries,
    update_library_version_documentation_urls_all_versions,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name"]
    ordering = ["name"]
    search_fields = ["name"]


@admin.register(CommitData)
class CommitDataAdmin(admin.ModelAdmin):
    list_display = (
        "library",
        "commit_count_formatted",
        "month_year_formatted",
        "branch",
        "library_link",
    )
    list_filter = ("library__name", "branch", "month_year")
    search_fields = ("library__name", "branch")
    date_hierarchy = "month_year"
    ordering = ("library__name", "-month_year")
    autocomplete_fields = ["library"]
    change_list_template = "admin/commit_data_change_list.html"

    def commit_count_formatted(self, obj):
        return f"{obj.commit_count:,}"

    commit_count_formatted.admin_order_field = "commit_count"
    commit_count_formatted.short_description = "Commit Count"

    def month_year_formatted(self, obj):
        return obj.month_year.strftime("%B %Y")

    month_year_formatted.admin_order_field = "month_year"
    month_year_formatted.short_description = "Month/Year"

    def library_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            reverse("admin:libraries_library_change", args=(obj.library.pk,)),
            obj.library.name,
        )

    library_link.short_description = "Library Details"

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "library":
            kwargs["queryset"] = Library.objects.order_by("name")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path(
                "update_commit_data/",
                self.update_commit_data,
                name="update_commit_data",
            ),
        ]
        return my_urls + urls

    def update_commit_data(self, request):
        """Run the task to refresh the library data from GitHub"""
        update_commit_counts.delay()
        self.message_user(
            request,
            """
            Commit data is being refreshed.
        """,
        )
        return HttpResponseRedirect("../")


@admin.register(Library)
class LibraryAdmin(admin.ModelAdmin):
    list_display = ["name", "key", "github_url"]
    search_fields = ["name", "description"]
    list_filter = ["categories"]
    ordering = ["name"]
    change_list_template = "admin/library_change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path("update_libraries/", self.update_libraries, name="update_libraries"),
        ]
        return my_urls + urls

    def update_libraries(self, request):
        """Run the task to refresh the library data from GitHub"""
        update_libraries.delay()
        self.message_user(
            request,
            """
            Library data is being refreshed.
        """,
        )
        return HttpResponseRedirect("../")


@admin.register(LibraryVersion)
class LibraryVersionAdmin(admin.ModelAdmin):
    list_display = ["library", "version", "documentation_url"]
    list_filter = ["library", "version"]
    ordering = ["library__name", "-version__name"]
    search_fields = ["library__name", "version__name"]
    change_list_template = "admin/libraryversion_change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path("update_docs_urls/", self.update_docs_urls, name="update_docs_urls"),
        ]
        return my_urls + urls

    def update_docs_urls(self, request):
        """Run the task to refresh the documentation URLS from S3"""
        update_library_version_documentation_urls_all_versions.delay()
        self.message_user(
            request,
            """
            Documentation links are being refreshed.
        """,
        )
        return HttpResponseRedirect("../")


@admin.register(Issue)
class IssueAdmin(admin.ModelAdmin):
    list_display = ["title", "number", "is_open", "closed"]
    search_fields = ["title"]
    list_filter = ["is_open", "library"]

    readonly_fields = [
        "title",
        "number",
        "github_id",
        "created",
        "modified",
        "closed",
    ]


@admin.register(PullRequest)
class PullRequestAdmin(admin.ModelAdmin):
    list_display = ["title", "number", "is_open", "closed"]
    search_fields = ["title"]
    list_filter = ["is_open", "library"]

    readonly_fields = [
        "title",
        "number",
        "github_id",
        "created",
        "modified",
        "closed",
    ]
