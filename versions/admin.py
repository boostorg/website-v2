from django.contrib import admin

from . import models


class VersionFileInline(admin.StackedInline):
    model = models.VersionFile
    autocomplete_fields = ("version",)
    verbose_name = "VersionFile"
    verbose_name_plural = "VersionFiles"
    extra = 0


@admin.register(models.Version)
class VersionAdmin(admin.ModelAdmin):
    list_display = ["name", "release_date", "active"]
    list_filter = ["active"]
    search_fields = ["name", "description"]
    date_hierarchy = "release_date"
    inlines = [VersionFileInline]
