from django.contrib import admin

from patches.models import LibraryPatch


# Register your models here.
@admin.register(LibraryPatch)
class LibraryPatchAdmin(admin.ModelAdmin):
    list_display = ["patch_name", "version", "library"]
    list_filter = ["version"]
