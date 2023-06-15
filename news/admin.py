from django.contrib import admin

from .models import NEWS_MODELS


class EntryAdmin(admin.ModelAdmin):
    list_display = ["title", "author", "created_at", "approved_at", "publish_at"]
    readonly_fields = ["modified_at", "is_approved", "is_published"]
    prepopulated_fields = {"slug": ["title"]}


for news_model in NEWS_MODELS:
    admin.site.register(news_model, EntryAdmin)
