from libraries.path_matcher.base_path_matcher import PathMatchResult
from libraries.path_matcher.matchers import (
    DirectMatcher,
    LibsPathToLatestDirectMatcher,
    LibsPathToLatestFallbackMatcher,
    LibsToAntoraPathDirectMatcher,
    DocHtmlBoostPathToFallbackMatcher,
    DocHtmlPathToDirectMatcher,
    DocHtmlBoostHtmlFallbackPathMatcher,
    ToLibsLatestRootFallbackMatcher,
)
from libraries.utils import get_s3_client
from versions.models import Version


def get_path_match_from_chain(url: str, latest_version: Version) -> PathMatchResult:
    s3_client = get_s3_client()

    # matcher chain in order
    matcher_classes = [
        DirectMatcher,
        LibsPathToLatestDirectMatcher,
        LibsToAntoraPathDirectMatcher,
        LibsPathToLatestFallbackMatcher,
        DocHtmlBoostPathToFallbackMatcher,
        DocHtmlPathToDirectMatcher,
        DocHtmlBoostHtmlFallbackPathMatcher,
        ToLibsLatestRootFallbackMatcher,
    ]

    matchers = [
        matcher_class(latest_version, s3_client) for matcher_class in matcher_classes
    ]
    for current, next_matcher in zip(matchers, matchers[1:]):
        current.set_next(next_matcher)
    result = matchers[0].handle(test_path=url)
    return result


def determine_latest_url(url: str, latest_version: Version) -> str:
    match_result = get_path_match_from_chain(url, latest_version)
    return match_result.latest_path
