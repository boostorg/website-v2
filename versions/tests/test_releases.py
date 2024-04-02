import responses
import pytest

from django.conf import settings

from ..models import VersionFile
from ..releases import (
    get_artifactory_download_data,
    get_archives_download_data,
    get_artifactory_download_uris_for_release,
    get_archives_download_uris_for_release,
    store_release_downloads_for_version,
)


@responses.activate
def test_get_artifactory_downloads_for_release():
    version_num = "1.81.0"
    url = f"{settings.ARTIFACTORY_URL}release/{version_num}/source/"
    data = {
        "children": [
            {"uri": "/boost_1_81_0.tar.bz2"},  # include
            {"uri": "/boost_1_81_0-rc.tar.gz"},  # exclude, release candidate
            {"uri": "/boost_1_81_0-beta.tar.gz"},  # exclude, beta
            {"uri": "/boost_1_81_0.html"},  # exclude, wrong extension
        ]
    }
    responses.add(responses.GET, url, json=data)
    downloads = get_artifactory_download_uris_for_release(version_num)
    assert len(downloads) == 1
    assert downloads[0] == f"{url}boost_1_81_0.tar.bz2"


@responses.activate
def test_get_archives_downloads_for_release():
    version_num = "1.81.0"
    url = f"{settings.ARCHIVES_URL}release/{version_num}/source/"
    data = """
<html><head><title>Index of /release/1.81.0/source/</title></head>
<body>
<h1>Index of /release/1.81.0/source/</h1><hr><pre><a href="../">../</a>
<a href="boost_1_81_0.7z">boost_1_81_0.7z</a> 15-Dec-2022 03:50           101553425
<a href="boost_1_81_0.7z.json">boost_1_81_0.7z.json</a>  15-Dec-2022 03:50    196
<a href="boost_1_81_0.tar.bz2">boost_1_81_0.tar.bz2</a>   15-Dec-2022 03:50  118797750
<a href="boost_1_81_0.tar.bz2.json">boost_1_81_0.tar.bz2.json</a> 15-Dec-2022 03:50 201
<a href="boost_1_81_0.tar.gz">boost_1_81_0.tar.gz</a> 15-Dec-2022 03:50  140221178
<a href="boost_1_81_0.tar.gz.json">boost_1_81_0.tar.gz.json</a> 15-Dec-2022 03:50  200
<a href="boost_1_81_0.zip">boost_1_81_0.zip</a> 15-Dec-2022 03:50  204805644
<a href="boost_1_81_0.zip.json">boost_1_81_0.zip.json</a>   15-Dec-2022 03:50  197
<a href="boost_1_81_0_rc1.7z">boost_1_81_0_rc1.7z</a>   09-Dec-2022 03:47 101553425
<a href="boost_1_81_0_rc1.7z.json">boost_1_81_0_rc1.7z.json</a> 09-Dec-2022 03:47 200
</pre><hr>

</body></html>
    """
    responses.add(responses.GET, url, body=data)
    downloads = get_archives_download_uris_for_release(version_num)
    assert len(downloads) == 4
    assert downloads[0] == f"{url}boost_1_81_0.7z"


@responses.activate
def test_get_artifactory_downloads_for_release_beta():
    version_num = "1.81.0.beta1"
    url = f"{settings.ARTIFACTORY_URL}beta/{version_num}/source/"
    data = {
        "children": [
            {"uri": "/boost_1_81_0.tar.bz2"},  # include, because not excluded
            {"uri": "/boost_1_81_0-rc.tar.gz"},  # exclude, release candidate
            {"uri": "/boost_1_81_0-beta.tar.gz"},  # include, beta
            {"uri": "/boost_1_81_0.html"},  # exclude, wrong extension
        ]
    }
    responses.add(responses.GET, url, json=data)
    downloads = get_artifactory_download_uris_for_release(version_num)
    assert len(downloads) == 2
    assert f"{url}boost_1_81_0-rc.tar.gz" not in downloads
    assert f"{url}boost_1_81_0.html" not in downloads


@responses.activate
def test_get_artifactory_download_data():
    url = "https://example.com/release/1.81.0/source/boost_1_81_0.tar.bz2"

    responses.add(
        responses.GET,
        url,
        json={"downloadUri": url, "checksums": {"sha256": "123"}},
    )
    data = get_artifactory_download_data(url)
    assert data["url"] == url
    assert data["operating_system"] == "Unix"
    assert data["checksum"] == "123"
    assert data["display_name"] == "boost_1_81_0.tar.bz2"


@responses.activate
def test_get_archives_download_data():
    url = "https://example.com/release/1.81.0/source/boost_1_81_0.tar.bz2"
    json_url = f"{url}.json"

    responses.add(responses.GET, json_url, json={"sha256": "123"})
    data = get_archives_download_data(url)
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
