import datetime
import hashlib
import pytest
import random

from model_bakery import baker

from versions.models import OperatingSystems


def fake_checksum():
    return hashlib.sha256(random.randbytes(200)).hexdigest()


@pytest.fixture
def beta_version(db):
    # Make version
    v = baker.make(
        "versions.Version",
        name="boost-1.79.0-beta",
        description="Some awesome description of the library",
        release_date=datetime.date.today(),
        beta=True,
        fully_imported=True,
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
        name="boost-1.79.0",
        description="Some awesome description of the library",
        release_date=yesterday,
        fully_imported=True,
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
def not_imported_version(db):
    # Make version that is not fully imported
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    v = baker.make(
        "versions.Version",
        name="boost-1.80.0",
        description="A version that is not fully imported",
        release_date=yesterday,
        fully_imported=False,
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
        name="boost-1.0.0",
        description="Some old description of the library",
        release_date=yesterday,
        active=False,
        fully_imported=True,
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
        name="boost-1.70.0",
        description="Some awesome description of the library",
        release_date=last_year,
        fully_imported=True,
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
        name="boost-1.79.0",
        description="Some old description of the library for v1.79.0",
        release_date=yesterday,
        active=False,
        fully_imported=True,
    )

    f1_url = f"{base_url}version1{base_url_suffix}"
    c1 = fake_checksum()
    baker.make(
        "versions.VersionFile",
        version=v,
        operating_system=OperatingSystems.UNIX,
        url=f1_url,
        checksum=c1,
    )

    f2_url = f"{base_url}version1_2{base_url_suffix}"
    c2 = fake_checksum()
    baker.make(
        "versions.VersionFile",
        version=v,
        operating_system=OperatingSystems.UNIX,
        url=f2_url,
        checksum=c2,
    )

    f3_url = f"{base_url}version1_3{base_url_suffix}"
    c3 = fake_checksum()
    baker.make(
        "versions.VersionFile",
        version=v,
        operating_system=OperatingSystems.WINDOWS,
        url=f3_url,
        checksum=c3,
    )

    return v
