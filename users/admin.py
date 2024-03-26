from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from .models import User


class EmailUserAdmin(UserAdmin):
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            _("Personal info"),
            {
                "fields": (
                    "first_name",
                    "last_name",
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
                    "image",
                )
            },
        ),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),
    )
    ordering = ("email",)
    list_display = (
        "email",
        "first_name",
        "last_name",
        "is_staff",
        "valid_email",
        "claimed",
    )
    search_fields = ("email", "first_name", "last_name")


admin.site.register(User, EmailUserAdmin)
