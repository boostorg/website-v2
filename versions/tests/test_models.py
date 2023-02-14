import datetime

from model_bakery import baker


def test_version_creation(version):
    today = datetime.date.today()
    assert version.release_date < today


def test_version_slug(version):
    version.name = "New Name"
    version.slug = None
    version.save()
    version.refresh_from_db()
    assert version.slug is not None
    assert version.slug == "new-name"


def test_version_get_slug(db):
    version = baker.prepare("versions.Version", name="Sample Library")
    assert version.get_slug() == "sample-library"


def test_version_file_creation(full_version_one):
    assert full_version_one.files.count() == 3
