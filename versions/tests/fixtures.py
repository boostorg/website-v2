import datetime
import hashlib
import pytest
import random

from model_bakery import baker

from versions.models import VersionFile


def fake_checksum():
    return hashlib.sha256(random.randbytes(200)).hexdigest()


@pytest.fixture
def beta_version(db):
    # Make version
    v = baker.make(
        "versions.Version",
        name="Version 1.79.0-beta",
        description="Some awesome description of the library",
        release_date=datetime.date.today(),
        beta=True,
    )

    # Make version download file
    c = fake_checksum()
    baker.make(
        "versions.VersionFile",
        version=v,
        checksum=c,
        url="https://example.com/version_1.tar.gz",
    )

    return v


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

    # Make version download file
    c = fake_checksum()
    baker.make(
        "versions.VersionFile",
        version=v,
        checksum=c,
        url="https://example.com/version_1.tar.gz",
    )

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

    # Make version download file
    c = fake_checksum()
    baker.make(
        "versions.VersionFile",
        version=v,
        checksum=c,
        url="https://example.com/old_version.tar.gz",
    )

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

    # Make version download file
    c = fake_checksum()
    baker.make(
        "versions.VersionFile",
        version=v,
        checksum=c,
        url="https://example.com/version_1_fake.tar.gz",
    )
    return v


@pytest.fixture
def full_version_one(db):
    """Build a full version with 3 attached files"""
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    base_url = "https://example.com/"
    base_url_suffix = ".tar.gz"
    v = baker.make(
        "versions.Version",
        name="1.79.0",
        description="Some old description of the library for v1.79.0",
        release_date=yesterday,
        active=False,
    )

    f1_url = f"{base_url}version1{base_url_suffix}"
    c1 = fake_checksum()
    baker.make(
        "versions.VersionFile",
        version=v,
        operating_system=VersionFile.Unix,
        url=f1_url,
        checksum=c1,
    )

    f2_url = f"{base_url}version1_2{base_url_suffix}"
    c2 = fake_checksum()
    baker.make(
        "versions.VersionFile",
        version=v,
        operating_system=VersionFile.Unix,
        url=f2_url,
        checksum=c2,
    )

    f3_url = f"{base_url}version1_3{base_url_suffix}"
    c3 = fake_checksum()
    baker.make(
        "versions.VersionFile",
        version=v,
        operating_system=VersionFile.Windows,
        url=f3_url,
        checksum=c3,
    )

    return v
