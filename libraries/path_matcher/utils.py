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

# matcher chain in order
MATCHER_CLASSES = [
    DirectMatcher,
    LibsPathToLatestDirectMatcher,
    LibsToAntoraPathDirectMatcher,
    LibsPathToLatestFallbackMatcher,
    DocHtmlBoostPathToFallbackMatcher,
    DocHtmlPathToDirectMatcher,
    DocHtmlBoostHtmlFallbackPathMatcher,
    ToLibsLatestRootFallbackMatcher,
]

EQUIVALENT_MATCHER_NAMES = {
    matcher_class.__name__
    for matcher_class in MATCHER_CLASSES
    if not matcher_class.is_index_fallback
}


def is_equivalent_page_match(matcher_name: str) -> bool:
    """Whether the matcher found the same page in the latest docs, rather than
    falling back to an index page.

    Unknown names, e.g. from a matcher that has since been removed, count as
    not equivalent.
    """
    return matcher_name in EQUIVALENT_MATCHER_NAMES


def get_path_match_from_chain(url: str, latest_version: Version) -> PathMatchResult:
    s3_client = get_s3_client()

    matchers = [
        matcher_class(latest_version, s3_client) for matcher_class in MATCHER_CLASSES
    ]
    for current, next_matcher in zip(matchers, matchers[1:]):
        current.set_next(next_matcher)
    result = matchers[0].handle(test_path=url)
    return result


def determine_latest_url(url: str, latest_version: Version) -> str:
    match_result = get_path_match_from_chain(url, latest_version)
    return match_result.latest_path
