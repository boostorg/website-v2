from datetime import timedelta

import requests
from django.contrib.postgres.fields import DateRangeField
from django.db import models
from django.db.backends.postgresql.psycopg_any import DateRange
from django_extensions.db.models import TimeStampedModel

from versions.models import Version

INCLUSIVE = "[]"

# TODO: keeping things simple for now, but should add comparison metrics


class WebsiteStatReport(TimeStampedModel):
    version = models.OneToOneField(Version, on_delete=models.CASCADE)
    period = DateRangeField()
    # comparison = DateRangeField()

    def __str__(self):
        return f"Stat report for {self.version}"

    def save(self, **kwargs):
        """Allow creation of reports while omitting period and/or version"""
        if self.version_id is None:
            self.version = Version.objects.most_recent()
        if not self.period:
            previous_version = (
                Version.objects.filter(
                    beta=False, release_date__lt=self.version.release_date
                )
                .order_by("-release_date")
                .first()
            )
            start_date = previous_version.release_date + timedelta(days=1)
            self.period = DateRange(start_date, self.version.release_date, INCLUSIVE)
        super().save(**kwargs)

    @property
    def analytics_api_url(self) -> str:
        domain = "preview.boost.org"  # this could change
        return (
            f"https://plausible.io/api/stats/{domain}/top-stats/?period=custom"
            f"&from={self.period.lower:%Y-%m-%d}&to={self.period.upper:%Y-%m-%d}"
        )

    def populate_from_api(self):
        """Fetch stats from API and generate child WebsiteStatItem instances."""

        response = requests.get(self.analytics_api_url)
        data = response.json()

        if not data or "top_stats" not in data:
            raise ValueError(f"Invalid Plausible API response: {data}")

        # Clear existing stat items
        WebsiteStatItem.objects.filter(report=self).delete()

        stat_items = []

        for stat_data in data["top_stats"]:
            stat = WebsiteStatItem(
                report=self,
                name=stat_data["name"],
                value=stat_data["value"],
                code_name=stat_data["graph_metric"],
            )
            stat_items.append(stat)

        WebsiteStatItem.objects.bulk_create(stat_items)


class WebsiteStatItem(TimeStampedModel):
    """Individual stat item (e.g. unique visitors)"""

    report = models.ForeignKey(
        WebsiteStatReport, on_delete=models.CASCADE, related_name="stats"
    )
    name = models.CharField()
    code_name = models.CharField()
    value = models.FloatField()
    # comparison_value = models.FloatField()

    def __str__(self):
        return f"{self.report.version} {self.name}"

    @property
    def formatted_value(self) -> str:
        """Format value based on metric type"""
        if self.code_name == "visit_duration":
            minutes, seconds = divmod(int(self.value), 60)
            return f"{minutes}m {seconds}s"
        elif self.code_name == "bounce_rate":
            return f"{self.value}%"
        return str(self.value)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["report", "code_name"], name="unique_report_code_name"
            )
        ]
