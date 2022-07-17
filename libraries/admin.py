from django.contrib import admin

from .models import Category, Library, Issue, PullRequest


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]


@admin.register(Library)
class LibraryAdmin(admin.ModelAdmin):
    list_display = ["name", "active_development", "open_issues"]
    search_fields = ["name", "description"]
    list_filter = ["active_development", "categories"]

    readonly_fields = [
        "last_github_update",
        "closed_prs_per_month",
        "open_issues",
        "commits_per_release",
    ]


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
