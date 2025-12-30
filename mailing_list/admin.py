import csv
import logging
import re
from datetime import datetime
from io import TextIOWrapper

from django import forms
from django.shortcuts import redirect, render
from django.urls import path
from django.http import HttpResponseRedirect
from django.contrib import admin, messages
from django.conf import settings

from mailing_list.models import EmailData, PostingData, SubscriptionData
from mailing_list.tasks import sync_mailinglist_stats

logger = logging.getLogger(__name__)


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


@admin.register(PostingData)
class PostingDataAdmin(admin.ModelAdmin):
    list_display = ["name", "post_time"]
    search_fields = ["name"]
    list_filter = ["post_time"]


class SubscribesCSVForm(forms.Form):
    csv_file = forms.FileField()


@admin.register(SubscriptionData)
class SubscriptionDataAdmin(admin.ModelAdmin):
    list_display = ["subscription_dt", "email"]
    search_fields = ["email"]
    change_list_template = "admin/mailinglist_change_list.html"

    email_regex = re.compile("([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})")

    def get_urls(self):
        return [
            path("import-csv", self.import_csv, name="import_csv")
        ] + super().get_urls()

    def parse_rows(self, reader):
        for row in reader:
            date_str = " ".join(row[0:4])
            try:
                dt = datetime.strptime(date_str, "%b %d %H:%M:%S %Y")
            except ValueError:
                logger.error(f"Error parsing date {date_str} from {row=}")
                dt = None
            # re-merge, the email address isn't always in a consistent position
            email_matches = re.search(self.email_regex, " ".join(row[6:]))
            email = email_matches.group(0) if email_matches else None
            entry_type = row[6]
            # only save confirmed subscriber entries, it's all we need for now
            if entry_type != "new":
                continue
            if not email:
                logger.error(
                    f"Invalid email {row=} {email_matches=} {' '.join(row[6:])=}"
                )
                continue
            yield SubscriptionData(
                email=email,
                entry_type=entry_type,
                list=row[5].rstrip(":-1"),
                subscription_dt=dt,
            )

    def import_csv(self, request):
        if request.method == "POST":
            csv_file = request.FILES["csv_file"]
            rows = TextIOWrapper(csv_file, encoding="ISO-8859-1", newline="")
            reader = csv.reader(rows, delimiter=" ")
            SubscriptionData.objects.bulk_create(
                self.parse_rows(reader), batch_size=500, ignore_conflicts=True
            )
            self.message_user(request, "Subscribe CSV file imported.")
            return redirect("..")

        payload = {"form": SubscribesCSVForm()}
        return render(request, "admin/mailinglist_subscribe_csv_form.html", payload)
