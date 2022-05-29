import datetime


def test_version_creation(version):
    today = datetime.date.today()
    assert version.release_date < today


def test_version_file_creation(full_version_one):
    assert full_version_one.files.count() == 3
