import datetime

from dateutil.relativedelta import relativedelta

from django.db import models
from django.db.models import Sum
from django.db.models.functions import ExtractYear


class CommitDataManager(models.Manager):
    def get_annual_commit_data_for_library(self, library, branch="master"):
        """Get the numbers of commits per year to a library and a branch."""
        return (
            self.filter(library=library, branch=branch)
            .annotate(year=ExtractYear("month_year"))
            .values("year")
            .annotate(commit_count=Sum("commit_count"))
            .order_by("year")
        )

    def get_commit_data_for_last_12_months_for_library(self, library, branch="master"):
        """Get the number of commits per month for the last 12 months to a library
        and a branch."""
        today = datetime.date.today()
        one_year_ago = today - relativedelta(years=1)
        return (
            self.filter(
                library=library,
                month_year__range=(one_year_ago, today),
                branch=branch,
            )
            .values("month_year")
            .annotate(commit_count=Sum("commit_count"))
            .order_by("month_year")
        )
