import responses
import pytest

from django.conf import settings

from ..models import VersionFile
from ..releases import (
    get_artifactory_download_data,
    get_artifactory_downloads_for_release,
    store_release_downloads_for_version,
)


@responses.activate
def test_get_artifactory_downloads_for_release():
    version_num = "1.81.0"
    url = f"{settings.ARTIFACTORY_URL}release/{version_num}/source/"
    data = {
        "children": [
            {"uri": "boost_1_81_0.tar.bz2"},  # include
            {"uri": "boost_1_81_0-rc.tar.gz"},  # exclude, release candidate
            {"uri": "boost_1_81_0-beta.tar.gz"},  # exclude, beta
            {"uri": "boost_1_81_0.html"},  # exclude, wrong extension
        ]
    }
    responses.add(responses.GET, url, json=data)
    downloads = get_artifactory_downloads_for_release(version_num)
    assert len(downloads) == 1
    assert downloads[0] == f"{url}boost_1_81_0.tar.bz2"


@responses.activate
def test_get_artifactory_download_data():
    url = "https://example.com/release/1.81.0/source/boost_1_81_0.tar.bz2"
    responses.add(
        responses.GET, url, json={"downloadUri": url, "checksums": {"sha256": "123"}}
    )
    data = get_artifactory_download_data(url)
    assert data["url"] == url
    assert data["operating_system"] == "Unix"
    assert data["checksum"] == "123"
    assert data["display_name"] == "boost_1_81_0.tar.bz2"


@responses.activate
def test_get_artifactory_download_data_value_error():
    url = "https://example.com/release/1.81.0/source/boost_1_81_0.tar.bz2"
    responses.add(responses.GET, url, json={"downloadUri": url})
    with pytest.raises(ValueError):
        get_artifactory_download_data(url)


def test_store_release_downloads_for_version(version):
    count = VersionFile.objects.filter(version=version).count()
    data = [
        {
            "url": "https://boostorg.jfrog.io/artifactory/main/release/1.81.0/source/boost_1_81_0.tar.bz2",
            "operating_system": "Unix",
            "checksum": "123",
            "display_name": "boost_1_81_0.tar.bz2",
        },
        {
            "url": "https://boostorg.jfrog.io/artifactory/main/release/1.81.0/source/boost_1_81_0.tar.gz",
            "operating_system": "Unix",
            "checksum": "456",
            "display_name": "boost_1_81_0.tar.gz",
        },
    ]
    store_release_downloads_for_version(version, data)
    assert VersionFile.objects.filter(version=version).count() == count + 2
    assert VersionFile.objects.filter(version=version, checksum="123").exists()
    assert VersionFile.objects.filter(version=version, checksum="456").exists()
