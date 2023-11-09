from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import path

from .models import Category, Issue, Library, LibraryVersion, PullRequest
from .tasks import update_libraries


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name"]
    ordering = ["name"]
    search_fields = ["name"]


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
        update_libraries.delay(update_all=True)
        self.message_user(
            request,
            """
            Library data is being refreshed.
        """,
        )
        return HttpResponseRedirect("../")


@admin.register(LibraryVersion)
class LibraryVersionAdmin(admin.ModelAdmin):
    list_display = ["library", "version"]
    list_filter = ["library", "version"]
    ordering = ["library__name", "-version__name"]
    search_fields = ["library__name", "version__name"]


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
