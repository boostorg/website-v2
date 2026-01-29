from django.contrib import admin
from django.urls import path
from django.shortcuts import redirect, render
from django.contrib import messages
from .models import RenderedContent, SiteSettings
from .tasks import delete_all_rendered_content


@admin.register(RenderedContent)
class RenderedContentAdmin(admin.ModelAdmin):
    list_display = ("cache_key", "content_type", "modified")
    search_fields = ("cache_key",)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "delete-all/",
                self.admin_site.admin_view(self.delete_all_view),
                name="core_renderedcontent_delete_all",
            ),
        ]
        return custom_urls + urls

    def delete_all_view(self, request):
        if request.method == "POST":
            delete_all_rendered_content.delay()
            messages.success(
                request,
                "Mass deletion task has been queued. All rendered content "
                "records will be deleted in batches. This may take some time.",
            )
            return redirect("..")

        context = {
            **self.admin_site.each_context(request),
            "title": "Delete All Rendered Content",
        }
        return render(
            request, "admin/core/renderedcontent/delete_all_confirmation.html", context
        )

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["has_delete_all"] = True
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ("id", "wordcloud_ignore")

    def has_add_permission(self, request):
        return super().has_add_permission(request) and SiteSettings.objects.count() == 0

    def has_delete_permission(self, request, obj=None):
        return False
