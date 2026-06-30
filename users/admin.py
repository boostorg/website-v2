from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.http import HttpResponseRedirect
from django.urls import path
from django.utils.translation import gettext_lazy as _

from .models import GithubActivity, User


class GithubActivityInline(admin.StackedInline):
    model = GithubActivity
    extra = 0
    can_delete = False
    readonly_fields = ("last_synced", "data")
    fields = ("last_synced", "data")
    verbose_name_plural = "GitHub Activity (cached)"

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(GithubActivity)
class GithubActivityAdmin(admin.ModelAdmin):
    list_display = ("user", "last_synced")
    readonly_fields = ("user", "last_synced", "data")
    search_fields = ("user__email", "user__github_username")


@admin.register(User)
class EmailUserAdmin(UserAdmin):
    change_form_template = "admin/user_change_form.html"
    inlines = [GithubActivityInline]

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            _("Personal info"),
            {
                "fields": (
                    "display_name",
                    "github_username",
                    "valid_email",
                    "claimed",
                )
            },
        ),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
        (_("Data"), {"fields": ("data",)}),
        (
            _("Image"),
            {
                "fields": (
                    "can_update_image",
                    "profile_image",
                )
            },
        ),
        (
            _("High Quality Image"),
            {"fields": ("hq_image",)},
        ),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),
    )
    ordering = ("email",)
    list_display = (
        "email",
        "display_name",
        "is_staff",
        "valid_email",
        "claimed",
    )
    search_fields = ("email", "display_name__unaccent")

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<int:user_pk>/refresh_github_activity/",
                self.admin_site.admin_view(self.refresh_github_activity_view),
                name="user_refresh_github_activity",
            ),
        ]
        return custom + urls

    def refresh_github_activity_view(self, request, user_pk):
        from users.tasks import refresh_github_activity

        try:
            user = User.objects.get(pk=user_pk)
        except User.DoesNotExist:
            self.message_user(request, "User not found.", level="error")
            return HttpResponseRedirect("../../")

        if not user.github_username:
            self.message_user(
                request,
                f"User {user} has no GitHub username set - cannot fetch activity.",
                level="warning",
            )
        else:
            refresh_github_activity.delay(user_pk)
            self.message_user(
                request,
                f"GitHub activity refresh queued for @{user.github_username}. "
                "Reload this page in a few seconds to see the result.",
            )

        return HttpResponseRedirect("../")
