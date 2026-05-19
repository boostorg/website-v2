from datetime import timedelta

import requests
import structlog
from django.contrib.postgres.fields import DateRangeField
from django.conf import settings
from django.db import models
from django.db.backends.postgresql.psycopg_any import DateRange
from django_extensions.db.models import TimeStampedModel

from reports.constants import (
    WEB_ANALYTICS_API_URL_V2,
    WEB_ANALYSTICS_API_TOP_STATS_PAYLOAD,
    WEB_ANALYTICS_CODENAME_MAPPING,
)
from versions.models import Version

INCLUSIVE = "[]"

logger = structlog.get_logger()


class WebsiteStatReport(TimeStampedModel):
    version = models.OneToOneField(Version, on_delete=models.CASCADE)
    period = DateRangeField()

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
    def analytics_api_payload(self):
        base_payload = WEB_ANALYSTICS_API_TOP_STATS_PAYLOAD
        base_payload["date_range"] = [str(self.period.lower), str(self.period.upper)]
        return base_payload

    def populate_from_api(self):
        """Fetch stats from API and generate child WebsiteStatItem instances."""

        if not settings.PLAUSIBLE_STATS_KEY:
            logger.info("Plausible API key not set, skipping")
            return

        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {settings.PLAUSIBLE_STATS_KEY}",
        }
        response = requests.post(
            url=WEB_ANALYTICS_API_URL_V2,
            json=self.analytics_api_payload,
            headers=headers,
        )
        data = response.json()

        if not data or "results" not in data or "query" not in data:
            raise ValueError(f"Invalid Plausible API response: {data}")

        # Clear existing stat items
        WebsiteStatItem.objects.filter(report=self).delete()

        stat_items = []

        for i, value in enumerate(data["query"]["metrics"]):
            code_name = value
            name = WEB_ANALYTICS_CODENAME_MAPPING.get(code_name, "")
            met_value = data["results"][0]["metrics"][i]

            stat = WebsiteStatItem(
                report=self,
                name=name,
                value=met_value,
                code_name=code_name,
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
