from django.contrib import admin
from .models import RenderedContent, SiteSettings


@admin.register(RenderedContent)
class RenderedContentAdmin(admin.ModelAdmin):
    list_display = ("cache_key", "content_type", "modified")
    search_fields = ("cache_key",)


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ("id", "wordcloud_ignore")

    def has_add_permission(self, request):
        return super().has_add_permission(request) and SiteSettings.objects.count() == 0

    def has_delete_permission(self, request, obj=None):
        return False
