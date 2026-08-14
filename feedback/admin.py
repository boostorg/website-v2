import json

from django.contrib import admin
from django.utils.html import format_html
from django.utils.text import Truncator
from import_export import fields, resources
from import_export.admin import ExportMixin

from feedback.models import Feedback


class FeedbackResource(resources.ModelResource):
    created_at = fields.Field(column_name="Submitted at", attribute="created_at")
    feedback_type = fields.Field(column_name="Type", attribute="feedback_type")
    status = fields.Field(column_name="Status", attribute="status")
    source = fields.Field(column_name="Source", attribute="source")
    submitter = fields.Field(column_name="Submitter", attribute="submitter")
    email = fields.Field(column_name="Submitter email", attribute="user__email")
    message = fields.Field(column_name="Message", attribute="message")
    image = fields.Field(column_name="Screenshot", attribute="image")
    page_url = fields.Field(column_name="Page", attribute="page_url")
    url_name = fields.Field(column_name="Route", attribute="url_name")
    boost_version = fields.Field(column_name="Boost version", attribute="boost_version")
    user_agent = fields.Field(column_name="User agent", attribute="user_agent")
    diagnostics = fields.Field(column_name="Diagnostics", attribute="diagnostics")

    def get_queryset(self, queryset):
        # `submitter` and the email column both walk to the user on every row.
        return queryset.select_related("user")

    class Meta:
        model = Feedback
        fields = (
            "created_at",
            "feedback_type",
            "status",
            "source",
            "submitter",
            "email",
            "message",
            "image",
            "page_url",
            "url_name",
            "boost_version",
            "user_agent",
            "diagnostics",
        )
        export_order = fields


@admin.register(Feedback)
class FeedbackAdmin(ExportMixin, admin.ModelAdmin):
    """Triage surface for beta feedback. Export only — importing would corrupt the dataset."""

    resource_class = FeedbackResource
    list_display = (
        "created_at",
        "feedback_type",
        "status",
        "source",
        "submitter",
        "short_message",
        "screenshot",
        "had_server_error",
        "url_name",
        "boost_version",
        "page_link",
    )
    list_editable = ("status",)
    # `submitter` reads obj.user on every row, which is a query each without this.
    list_select_related = ("user",)
    # url_name/boost_version are the grouping axes: "every complaint on the library
    # detail route", rather than one row per distinct URL string.
    list_filter = (
        "feedback_type",
        "status",
        "source",
        "url_name",
        "boost_version",
        "created_at",
    )
    search_fields = ("message", "user__email", "page_url")
    date_hierarchy = "created_at"
    readonly_fields = (
        "feedback_type",
        "message",
        "image",
        "user",
        "source",
        "page_url",
        "url_name",
        "boost_version",
        "user_agent",
        "pretty_diagnostics",
        "created_at",
    )
    exclude = ("diagnostics",)

    def has_add_permission(self, request):
        """Feedback only arrives from the widget; every other field is read-only here."""
        return False

    @admin.display(description="Message")
    def short_message(self, obj):
        return Truncator(obj.message).chars(80)

    @admin.display(description="Screenshot")
    def screenshot(self, obj):
        if not obj.image:
            return "—"
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">'
            '<img src="{}" alt="" style="max-height:40px;max-width:80px"></a>',
            obj.image.url,
            obj.image.url,
        )

    @admin.display(description="Server error", boolean=True)
    def had_server_error(self, obj):
        """Surfaces the highest-signal reports without opening every row."""
        return bool(obj.diagnostics.get("server_errors"))

    @admin.display(description="Browser diagnostics")
    def pretty_diagnostics(self, obj):
        if not obj.diagnostics:
            return "—"
        return format_html(
            '<pre style="white-space:pre-wrap;margin:0">{}</pre>',
            json.dumps(obj.diagnostics, indent=2, sort_keys=True),
        )

    @admin.display(description="Page")
    def page_link(self, obj):
        if not obj.page_url:
            return "—"
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">{}</a>',
            obj.page_url,
            Truncator(obj.page_url).chars(60),
        )
