from django.contrib import admin
from django.db.models import Count

from .models import (
    Email,
    GitContribution,
    GitProfile,
    GithubContribution,
    GithubProfile,
    Identity,
    Wg21Contribution,
    Wg21Profile,
)


class ReadOnlyInlineMixin:
    """Base mixin for read-only inline admin classes."""

    extra = 0
    readonly_fields = ["created", "modified"]


class ReadOnlyAdminMixin:
    """Base mixin for read-only admin classes."""

    readonly_fields = ["created", "modified"]

    def has_add_permission(self, request):
        return False


class GitProfileInline(ReadOnlyInlineMixin, admin.TabularInline):
    model = GitProfile
    fields = ["name", "email", "identity"]
    autocomplete_fields = ["email", "identity"]


class GithubProfileInline(ReadOnlyInlineMixin, admin.TabularInline):
    model = GithubProfile
    fields = ["name", "github_user_id", "identity"]
    autocomplete_fields = ["identity"]


class Wg21ProfileInline(ReadOnlyInlineMixin, admin.TabularInline):
    model = Wg21Profile
    fields = ["name", "identity"]
    autocomplete_fields = ["identity"]


class GithubContributionInline(ReadOnlyInlineMixin, admin.TabularInline):
    model = GithubContribution
    fields = ["type", "contributed_at", "repo", "info"]


class Wg21ContributionInline(ReadOnlyInlineMixin, admin.TabularInline):
    model = Wg21Contribution
    fields = ["info", "comment", "contributed_at"]


class GitContributionInline(ReadOnlyInlineMixin, admin.TabularInline):
    model = GitContribution
    fields = ["contributed_at", "repo", "info", "comment"]


@admin.register(Email)
class EmailAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ["email", "git_profile_count", "created"]
    search_fields = ["email"]
    ordering = ["-created"]
    inlines = [GitProfileInline]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(_git_profile_count=Count("git_profiles", distinct=True))
        )

    @admin.display(
        description="Git Profiles",
        ordering="_git_profile_count",
    )
    def git_profile_count(self, obj):
        return obj._git_profile_count


class ProfileTypeFilter(admin.SimpleListFilter):
    """Filter identities by profile type."""

    title = "profile type"
    parameter_name = "profile_type"

    PROFILE_FILTERS = {
        "git": "gitprofile_profiles__isnull",
        "github": "githubprofile_profiles__isnull",
        "wg21": "wg21profile_profiles__isnull",
    }

    def lookups(self, request, model_admin):
        return (
            ("git", "Has Git Profile"),
            ("github", "Has GitHub Profile"),
            ("wg21", "Has WG21 Profile"),
        )

    def queryset(self, request, queryset):
        if filter_field := self.PROFILE_FILTERS.get(self.value()):
            return queryset.filter(**{filter_field: False}).distinct()
        return queryset


@admin.register(Identity)
class IdentityAdmin(admin.ModelAdmin):
    list_display = ["name", "profile_type", "needs_review", "created"]
    list_filter = [ProfileTypeFilter, "needs_review", "created"]
    search_fields = ["name", "description"]
    readonly_fields = ["created", "modified"]
    ordering = ["-created"]
    inlines = [GitProfileInline, GithubProfileInline, Wg21ProfileInline]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(
                _git_profile_count=Count("gitprofile_profiles", distinct=True),
                _github_profile_count=Count("githubprofile_profiles", distinct=True),
                _wg21_profile_count=Count("wg21profile_profiles", distinct=True),
            )
        )

    @admin.display(description="Profile Type")
    def profile_type(self, obj):
        if obj._git_profile_count > 0:
            return "Git"
        if obj._github_profile_count > 0:
            return "GitHub"
        if obj._wg21_profile_count > 0:
            return "WG21"
        return "—"


@admin.register(GithubProfile)
class GithubProfileAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ["name", "github_user_id", "identity", "created"]
    list_filter = ["created"]
    search_fields = ["name", "identity__name"]
    autocomplete_fields = ["identity"]
    ordering = ["-created"]
    inlines = [GithubContributionInline]


@admin.register(GitProfile)
class GitProfileAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ["name", "email", "identity", "created"]
    list_filter = ["created"]
    search_fields = ["name", "email__email", "identity__name"]
    autocomplete_fields = ["email", "identity"]
    ordering = ["-created"]
    inlines = [GitContributionInline]


@admin.register(Wg21Profile)
class Wg21ProfileAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ["name", "identity", "created"]
    list_filter = ["created"]
    search_fields = ["name", "identity__name"]
    autocomplete_fields = ["identity"]
    ordering = ["-created"]
    inlines = [Wg21ContributionInline]


@admin.register(GithubContribution)
class GithubContributionAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ["profile", "type", "repo", "contributed_at", "info", "created"]
    list_filter = ["type", "contributed_at", "created"]
    search_fields = ["profile__name", "repo", "comment", "info"]
    autocomplete_fields = ["profile"]
    ordering = ["-contributed_at"]
    date_hierarchy = "contributed_at"


@admin.register(Wg21Contribution)
class Wg21ContributionAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ["profile", "info", "comment", "contributed_at", "created"]
    list_filter = ["contributed_at", "created"]
    search_fields = ["profile__name", "info", "comment"]
    autocomplete_fields = ["profile"]
    ordering = ["-contributed_at"]


@admin.register(GitContribution)
class GitContributionAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ["profile", "repo", "info", "contributed_at", "created"]
    list_filter = ["contributed_at", "created", "repo"]
    search_fields = [
        "profile__name",
        "profile__email__email",
        "repo",
        "comment",
        "info",
    ]
    autocomplete_fields = ["profile"]
    ordering = ["-contributed_at"]
    date_hierarchy = "contributed_at"
