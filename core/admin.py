from django.contrib import admin
from .models import RenderedContent


@admin.register(RenderedContent)
class RenderedContentAdmin(admin.ModelAdmin):
    list_display = ("cache_key", "content_type")
    search_fields = ("cache_key",)
