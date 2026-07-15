from collections import defaultdict

from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm
from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext_lazy as _

from .models import ProfileRole, User


class EmailUserAdminForm(UserChangeForm):
    """Admin change form for User.

    Staff assign the internal C++ Alliance title here (internal_role). Library
    roles (Author/Maintainer/Contributor) and the user's featured selection are
    derived from repo data / chosen by the user and shown read-only below.
    """

    class Meta(UserChangeForm.Meta):
        model = User
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["internal_role"].label = "C++ Alliance title"

    def clean_internal_role(self):
        """Block assigning a singular C++ Alliance title already held by someone.

        The partial unique index on the model is the hard guarantee; this names
        the current holder so staff know where to clear it first.
        """
        value = self.cleaned_data.get("internal_role", "")
        if value in ProfileRole.singular_roles():
            holder = (
                User.objects.exclude(pk=self.instance.pk)
                .filter(internal_role=value)
                .first()
            )
            if holder:
                raise forms.ValidationError(
                    f"{ProfileRole(value).label} is already assigned to "
                    f"{holder.display_name or holder.email}. Clear it from that "
                    "profile first."
                )
        return value


@admin.register(User)
class EmailUserAdmin(UserAdmin):
    form = EmailUserAdminForm
    readonly_fields = ("role_eligibility_display",)
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
                    "internal_role",
                    "role_eligibility_display",
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

    @admin.display(description=_("Derived library roles"))
    def role_eligibility_display(self, obj):
        """Read-only summary of the library roles the user holds.

        Sourced live from `User.get_role_library_options()`. This is what the
        user may feature; it is not editable here.
        """
        if obj is None or obj.pk is None:
            return "—"
        grouped = defaultdict(list)
        for option in obj.get_role_library_options():
            grouped[option["role"]].append(option["library"].name)
        if not grouped:
            return "—"
        return format_html_join(
            "",
            "<div><strong>{}</strong>: {}</div>",
            (
                (ProfileRole(role).label, ", ".join(sorted(libraries)))
                for role, libraries in grouped.items()
            ),
        ) or format_html("—")
