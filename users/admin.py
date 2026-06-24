from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import User


@admin.register(User)
class EmailUserAdmin(UserAdmin):
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            _("Personal info"),
            {
                "fields": (
                    "display_name",
                    "github_username",
                    "tagline",
                    "biography",
                    "valid_email",
                    "claimed",
                )
            },
        ),
        (_("Badges"), {"fields": ("badge_summary",)}),
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
    readonly_fields = ("badge_summary",)
    search_fields = ("email", "display_name__unaccent")

    @admin.display(description=_("Badges"))
    def badge_summary(self, obj):
        """Link out to the per-user badge page, which lives in the badges app.

        That page answers why each badge is or is not shown - below threshold,
        revoked, or hidden by the member - and is where a single member's badges
        are recalculated. This is only the way in from the user record.
        """
        if obj.pk is None:
            return _("Save the user first.")
        return format_html(
            '<a href="{}">{}</a>',
            reverse("admin:badges_userbadge_user_summary", args=[obj.pk]),
            _("View badges and achievements"),
        )
