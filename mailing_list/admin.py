from django.urls import path
from django.http import HttpResponseRedirect
from django.contrib import admin, messages
from django.conf import settings

from mailing_list.models import EmailData
from mailing_list.tasks import sync_mailinglist_stats


@admin.register(EmailData)
class EmailDataAdmin(admin.ModelAdmin):
    list_display = ["author", "version", "count"]
    search_fields = [
        "author__commitauthoremail__email",
        "author__name",
    ]
    raw_id_fields = ["author"]
    list_filter = ["version"]
    change_list_template = "admin/mailinglist_change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path(
                "sync_mailinglist_stats/",
                self.admin_site.admin_view(self.sync_mailinglist_stats),
                name="sync_mailinglist_stats",
            ),
        ]
        return my_urls + urls

    def sync_mailinglist_stats(self, request):
        if settings.HYPERKITTY_DATABASE_NAME:
            sync_mailinglist_stats.delay()
            self.message_user(request, "Syncing EmailData.")
        else:
            self.message_user(
                request,
                "HYPERKITTY_DATABASE_NAME setting not configured.",
                level=messages.WARNING,
            )
        return HttpResponseRedirect("../")

    def has_add_permission(self, request):
        return False
