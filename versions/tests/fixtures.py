import datetime
import hashlib
import pytest
import random

from pathlib import Path
from model_bakery import baker
from django.core.files import File
from django.core.files.base import ContentFile

from versions.models import VersionFile


def fake_checksum():
    return hashlib.sha256(random.randbytes(200)).hexdigest()


@pytest.fixture
def version(db):
    # Make version
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    v = baker.make(
        "versions.Version",
        name="Version 1.79.0",
        description="Some awesome description of the library",
        release_date=yesterday,
    )

    # Make verison file
    c = fake_checksum()
    f1 = ContentFile("Version 1 Fake Content")
    baker.make("versions.VersionFile", version=v, checksum=c, file=f1)

    return v


@pytest.fixture
def inactive_version(db):
    # Make version
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    v = baker.make(
        "versions.Version",
        name="Version 1.0.0",
        description="Some old description of the library",
        release_date=yesterday,
        active=False,
    )

    # Make verison file
    c = fake_checksum()
    f1 = ContentFile("Old Version Fake Content")
    baker.make("versions.VersionFile", version=v, checksum=c, file=f1)

    return v


@pytest.fixture
def old_version(db):
    # Make version
    last_year = datetime.date.today() - datetime.timedelta(days=365)
    v = baker.make(
        "versions.Version",
        name="Version 1.70.0",
        description="Some awesome description of the library",
        release_date=last_year,
    )

    # Make verison file
    c = fake_checksum()
    f1 = ContentFile("Version 1 Fake Content")
    baker.make("versions.VersionFile", version=v, checksum=c, file=f1)

    return v


def get_version_file_path(name):
    BASE_DIR = Path(__file__).parent
    return BASE_DIR.joinpath(f"files/{name}")


@pytest.fixture
def full_version_one(db):
    """Build a full version with 3 attached files"""
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    v = baker.make(
        "versions.Version",
        name="1.79.0",
        description="Some old description of the library for v1.79.0",
        release_date=yesterday,
        active=False,
    )

    vf1 = baker.prepare(
        "versions.VersionFile", version=v, operating_system=VersionFile.Unix
    )
    f1_path = get_version_file_path("version1.tar.gz")
    with open(f1_path, "rb") as f:
        vf1.file.save(f1_path.name, File(f), save=True)
        vf1.save()

    vf2 = baker.prepare(
        "versions.VersionFile", version=v, operating_system=VersionFile.Unix
    )
    f2_path = get_version_file_path("version1.tar.bz2")
    with open(f2_path, "rb") as f:
        vf2.file.save(f2_path.name, File(f), save=True)
        vf2.save()

    vf3 = baker.prepare(
        "versions.VersionFile", version=v, operating_system=VersionFile.Windows
    )
    f3_path = get_version_file_path("version1.zip")
    with open(f3_path, "rb") as f:
        vf3.file.save(f3_path.name, File(f), save=True)
        vf3.save()

    return v
