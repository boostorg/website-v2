from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
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
