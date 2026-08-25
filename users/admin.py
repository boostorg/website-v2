from collections import defaultdict

from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseNotAllowed, HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext_lazy as _

from .models import GithubActivity, ProfileRole, User


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
    form = EmailUserAdminForm
    readonly_fields = ("role_eligibility_display", "badge_summary")
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
                    "tagline",
                    "biography",
                    "internal_role",
                    "role_eligibility_display",
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

        # Queueing work must not be reachable by GET: browser prefetch, link
        # scanners and a plain page reload would all fire it, and GET carries
        # no CSRF token.
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])

        try:
            user = User.objects.get(pk=user_pk)
        except User.DoesNotExist:
            self.message_user(request, "User not found.", level="error")
            return HttpResponseRedirect("../../")

        # admin_view() only checks staff status, so any staff member could
        # otherwise queue a refresh for a user they cannot change.
        if not self.has_change_permission(request, user):
            raise PermissionDenied

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
