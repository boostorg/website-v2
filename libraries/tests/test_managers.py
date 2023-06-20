from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from model_bakery import baker

from ..models import CommitData


def test_get_annual_commit_data_for_library(library):
    five_years_ago = datetime.now().date().replace(year=datetime.now().year - 5)
    for i in range(5):
        date = five_years_ago.replace(year=five_years_ago.year + i)
        baker.make(
            "libraries.CommitData",
            library=library,
            month_year=date,
            commit_count=i + 1,
            branch="master",
        )

    result = CommitData.objects.get_annual_commit_data_for_library(library)
    assert len(result) == 5
    for i, data in enumerate(result):
        assert data["year"] == five_years_ago.year + i
        assert data["commit_count"] == i + 1


def test_get_commit_data_for_last_12_months_for_library(library):
    one_year_ago = datetime.now().date() - timedelta(days=365)
    for i in range(12):
        date = one_year_ago + relativedelta(months=i)
        baker.make(
            "libraries.CommitData",
            library=library,
            month_year=date,
            commit_count=i + 1,
            branch="master",
        )

    result = CommitData.objects.get_commit_data_for_last_12_months_for_library(library)
    assert len(result) == 12
    for i, data in enumerate(result):
        assert data["month_year"] == one_year_ago + relativedelta(months=i)
        assert data["commit_count"] == i + 1
