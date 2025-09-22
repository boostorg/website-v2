from django.contrib import admin
from django.contrib.auth import get_user_model

from core.admin_filters import StaffUserCreatedByFilter
from .models import SandboxDocument

User = get_user_model()


@admin.register(SandboxDocument)
class SandboxDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "created_by", "created_at", "updated_at")
    list_filter = ("created_at", "updated_at", StaffUserCreatedByFilter)
    search_fields = ("title", "asciidoc_content")
    readonly_fields = ("created_at", "updated_at", "created_by")
    ordering = ("-updated_at",)
    change_form_template = "admin/asciidoctor_sandbox_doc_change_form.html"

    fieldsets = (
        (None, {"fields": ("title", "asciidoc_content")}),
        (
            "Metadata",
            {
                "fields": ("created_by", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
