import re
import time
from urllib.parse import urljoin, urlencode


def get_base_url(base_url):
    return base_url or "https://www.boost.org"


def build_url(base_url, path="/", cachebust=False, params=None):
    url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    query_params = {}
    if cachebust:
        query_params["cachebust"] = str(int(time.time() * 1000))
    if params:
        query_params.update(params)
    if query_params:
        url += ("&" if "?" in url else "?") + urlencode(query_params)
    return url


class UrlPatterns:
    homepage = "/"
    libraries = "/libraries/"
    releases = "/releases/"
    documentation = "/doc/libs/"
    community = "/community/"
    search = "/search/"

    @staticmethod
    def doc_libs_version(version="1_85_0"):
        return f"/doc/libs/{version}/"

    @staticmethod
    def release_notes(version="1_85_0"):
        return f"/doc/libs/{version}/libs/release_notes/"


class ExpectedUrlPatterns:
    after_cta_click = re.compile(r"libraries|releases|docs|learn|download", re.I)
    after_search = re.compile(r"search|results|q=", re.I)
    after_logo_click = re.compile(r"/?$")
    github_boost = re.compile(r"github\.com/boostorg", re.I)
    download_site = re.compile(
        r"archives\.boost\.io|github\.com/boostorg/boost/releases|download|release",
        re.I,
    )
    community_links = re.compile(r"github.com.*issues|discourse|lists.boost.org", re.I)


url_patterns = UrlPatterns()
expected_url_patterns = ExpectedUrlPatterns()


class TestData:
    search_terms = {
        "working": "asio",
        "alternative": "algorithm",
    }
    download_files = {
        "tar_gz": re.compile(r"boost_1_74_0\.tar\.gz$"),
        "zip": re.compile(r"boost_1_85_0\.zip$"),
        "supported": re.compile(r"\.(zip|tar\.gz|tar\.bz2|7z|exe)$"),
    }
    timeouts = {
        "short": 5000,
        "medium": 15000,
        "long": 30000,
        "download": 60000,
    }
    viewport = {
        "desktop": {"width": 1280, "height": 720},
        "mobile": {"width": 800, "height": 600},
    }


test_data = TestData()
