import datetime


def test_version_creation(version):
    today = datetime.date.today()
    assert version.release_date < today
