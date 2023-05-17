from django.contrib import admin

from .models import Entry


class EntryAdmin(admin.ModelAdmin):
    list_display = ["title", "author", "created_at", "approved_at", "publish_at"]
    readonly_fields = ["modified_at"]
    prepopulated_fields = {"slug": ["title"]}


admin.site.register(Entry, EntryAdmin)
