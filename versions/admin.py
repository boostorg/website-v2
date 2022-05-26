from django.contrib import admin

from . import models


@admin.register(models.Version)
class VersionAdmin(admin.ModelAdmin):
    list_display = ["name", "release_date"]
    search_fields = [
        "name",
    ]
