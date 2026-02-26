import os
import re

from core.constants import BOOST_VERSION_REGEX
from libraries.constants import LATEST_RELEASE_URL_PATH_STR
from libraries.path_matcher import BasePathMatcher, PathSegments


class DirectMatcher(BasePathMatcher):
    # pseudo-example 1_84_0/*/CXX11.html
    # pseudo-expected s3 dest = static_content_1_79_0/*/CXX11.html e.g. 'static_content_1_90_0/doc/html/accumulators.html'
    # pseudo-expected final path = doc/libs/latest/*/CXX11.html
    has_equivalent = True
    path_re = re.compile(
        rf"{BOOST_VERSION_REGEX}/(?P<content_path>(?P<library_name>\S+))"
    )

    def generate_latest_s3_path(self, path: str, segments: PathSegments):
        return "/".join([f"static_content_{self.latest_slug}", segments.content_path])

    def generate_latest_url(self, path_data: PathSegments) -> str:
        return os.path.sep.join(
            ["doc", "libs", LATEST_RELEASE_URL_PATH_STR, path_data.content_path]
        )


class LibsPathToLatestDirectMatcher(BasePathMatcher):
    # example 1_84_0/libs/algorithm/doc/html/algorithm/CXX11.html
    # expected s3 dest = static_content_1_79_0/libs/algorithm/doc/html/algorithm/CXX11.html
    # expected final path = doc/libs/latest/libs/algorithm/doc/html/algorithm/CXX11.html
    has_equivalent = False
    path_re = re.compile(
        rf"{BOOST_VERSION_REGEX}/libs/(?P<library_name>[\w]+)/(?P<content_path>\S+)"
    )

    def generate_latest_s3_path(self, path: str, segments: PathSegments):
        return "/".join(
            [
                f"static_content_{self.latest_slug}",
                "libs",
                segments.library_name,
                segments.content_path,
            ]
        )

    def generate_latest_url(self, path_data: PathSegments) -> str:
        return os.path.sep.join(
            [
                "doc",
                "libs",
                LATEST_RELEASE_URL_PATH_STR,
                "libs",
                path_data.library_name,
                path_data.content_path,
            ]
        )


class LibsPathToLatestFallbackMatcher(BasePathMatcher):
    # example 	1_78_0/libs/algorithm/doc/html/header/boost/algorithm/string_regex_hpp.html
    # expected s3 dest = static_content_1_79_0/libs/algorithm/index.html
    # expected final path = doc/libs/latest/libs/algorithm/index.html
    path_re = re.compile(
        rf"{BOOST_VERSION_REGEX}/libs/(?P<library_name>[\w]+)/(?P<content_path>\S+)"
    )
    is_index_fallback = True

    def generate_latest_s3_path(self, path, segments: PathSegments):
        return "/".join(
            [
                f"static_content_{self.latest_slug}",
                "libs",
                segments.library_name,
                "index.html",
            ]
        )

    def generate_latest_url(self, path_data: PathSegments) -> str:
        return os.path.sep.join(
            [
                "doc",
                "libs",
                LATEST_RELEASE_URL_PATH_STR,
                "libs",
                path_data.library_name,
                "index.html",
            ]
        )


class LibsToAntoraPathDirectMatcher(BasePathMatcher):
    # example 1_85_0/libs/url/doc/html/url/urls/segments.html
    # expected s3 dest = static_content_1_79_0/doc/antora/url/urls/segments.html
    # expected final dest = doc/libs/latest/doc/antora/url/index.html

    # Only the boost urls library redirects to antora for now so the regex in use
    # is tightly limited to that. The commented path_re will work when this is
    # needed to be more generic, all other things being equal.
    # path_re = re.compile(rf"{BOOST_VERSION_REGEX}/libs/(?P<library_name>[\w]+)/(?P<content_path>\S+)")
    path_re = re.compile(
        rf"{BOOST_VERSION_REGEX}/libs/(?P<library_name>url)/(?P<content_path>\S+)"
    )

    def generate_latest_s3_path(self, path: str, segments: PathSegments) -> str:
        # library name is in content_path
        return "/".join(
            [
                f"static_content_{self.latest_slug}",
                "doc",
                "antora",
                segments.content_path.replace("doc/html/", ""),
            ]
        )

    def generate_latest_url(self, path_data: PathSegments) -> str:
        # library name is in content_path
        return os.path.sep.join(
            [
                "doc",
                "libs",
                LATEST_RELEASE_URL_PATH_STR,
                "doc",
                "antora",
                path_data.content_path.replace("doc/html/", ""),
            ]
        )


class DocHtmlBoostPathToFallbackMatcher(BasePathMatcher):
    # example 1_64_0/doc/html/boost_process/acknowledgements.html
    # expected s3 dest = static_content_1_79_0/libs/process/index.html
    # expected final path = doc/libs/latest/libs/process/index.html
    path_re = re.compile(
        rf"{BOOST_VERSION_REGEX}/doc/html/boost_(?P<library_name>[\w]+)/(?P<content_path>\S+)"
    )
    is_index_fallback = True

    def generate_latest_s3_path(self, path: str, segments: PathSegments) -> str:
        return "/".join(
            [
                f"static_content_{self.latest_slug}",
                "libs",
                segments.library_name,
                "index.html",
            ]
        )

    def generate_latest_url(self, path_data: PathSegments) -> str:
        return os.path.sep.join(
            [
                "doc",
                "libs",
                LATEST_RELEASE_URL_PATH_STR,
                "libs",
                path_data.library_name,
                "index.html",
            ]
        )


class DocHtmlPathToDirectMatcher(BasePathMatcher):
    # example = 1_35_0/doc/html/interprocess.html
    # expected s3 dest = static_content_1_79_0/doc/html/interprocess.html
    # expected final path = doc/libs/latest/doc/html/interprocess.html
    path_re = re.compile(
        rf"{BOOST_VERSION_REGEX}/(?P<content_path>doc/html/(?!boost_)(?P<library_name>[\w]+.html))"
    )

    def generate_latest_s3_path(self, path: str, segments: PathSegments) -> str:
        return "/".join([f"static_content_{self.latest_slug}", segments.content_path])

    def generate_latest_url(self, path_data: PathSegments) -> str:
        return os.path.sep.join(
            ["doc", "libs", LATEST_RELEASE_URL_PATH_STR, path_data.content_path]
        )


class DocHtmlBoostHtmlFallbackPathMatcher(BasePathMatcher):
    # example 1_34_0/doc/html/boost_math.html
    # expected s3 dest = static_content_1_79_0/libs/math/doc/html/index.html
    # expected final path = doc/libs/latest/libs/math/doc/html/index.html
    path_re = re.compile(
        rf"{BOOST_VERSION_REGEX}/(?P<content_path>doc/html)/boost_(?P<library_name>[\w]+).html"
    )
    is_index_fallback = True

    def generate_latest_s3_path(self, path: str, segments: PathSegments) -> str:
        return "/".join(
            [
                f"static_content_{self.latest_slug}",
                "libs",
                segments.library_name,
                segments.content_path,
                "index.html",
            ]
        )

    def generate_latest_url(self, path_data: PathSegments) -> str:
        return os.path.sep.join(
            [
                "doc",
                "libs",
                LATEST_RELEASE_URL_PATH_STR,
                "libs",
                path_data.library_name,
                path_data.content_path,
                "index.html",
            ]
        )


class ToLibsLatestRootFallbackMatcher(BasePathMatcher):
    # any other path not matched will arrive here, values inaccurate, set as needed
    path_re = re.compile(r"(?P<content_path>(?P<library_name>\S+))")
    is_index_fallback = True

    def generate_latest_s3_path(self, path: str, segments: PathSegments) -> str:
        return "/".join([f"static_content_{self.latest_slug}", "libs"])

    def generate_latest_url(self, path_data: PathSegments) -> str:
        # trailing slash here to save a redirect
        return f"libraries/{LATEST_RELEASE_URL_PATH_STR}/"
