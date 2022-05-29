import datetime
import hashlib
import pytest
import random

from model_bakery import baker
from django.core.files.base import ContentFile


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
    vf = baker.make("versions.VersionFile", version=v, checksum=c, file=f1)

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
    vf = baker.make("versions.VersionFile", version=v, checksum=c, file=f1)

    return v
