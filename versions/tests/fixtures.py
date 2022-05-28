import pytest
import datetime
from model_bakery import baker


@pytest.fixture
def version(db):
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    return baker.make(
        "versions.Version",
        name="Version 1.79.0",
        description="Some awesome description of the library",
        release_date=yesterday,
    )
