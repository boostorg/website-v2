from django.contrib import admin

from marketing.models import CapturedEmail


@admin.register(CapturedEmail)
class CapturedEmailAdmin(admin.ModelAdmin):
    model = CapturedEmail
    list_display = ("email", "referrer", "page")
