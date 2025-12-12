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
from versions.models import Version


def get_path_match_from_chain(url: str, latest_version: Version) -> PathMatchResult:
    # set up path check instances
    libs_direct_matcher = DirectMatcher(latest_version)
    libs_path_direct_matcher = LibsPathToLatestDirectMatcher(latest_version)
    libs_to_antora_matcher = LibsToAntoraPathDirectMatcher(latest_version)
    libs_path_fallback_matcher = LibsPathToLatestFallbackMatcher(latest_version)
    doc_html_boost_to_fallback_matcher = DocHtmlBoostPathToFallbackMatcher(
        latest_version
    )
    doc_html_path_direct_matcher = DocHtmlPathToDirectMatcher(latest_version)
    doc_html_lib_name_matcher = DocHtmlBoostHtmlFallbackPathMatcher(latest_version)
    final_fallback = ToLibsLatestRootFallbackMatcher(latest_version)

    # chain the handlers
    libs_direct_matcher.set_next(libs_path_direct_matcher)
    libs_path_direct_matcher.set_next(libs_to_antora_matcher)
    libs_to_antora_matcher.set_next(libs_path_fallback_matcher)
    libs_path_fallback_matcher.set_next(doc_html_boost_to_fallback_matcher)
    doc_html_boost_to_fallback_matcher.set_next(doc_html_path_direct_matcher)
    doc_html_path_direct_matcher.set_next(doc_html_lib_name_matcher)
    doc_html_lib_name_matcher.set_next(final_fallback)

    result = libs_direct_matcher.handle(test_path=url)
    return result


def determine_latest_url(url: str, latest_version: Version) -> str:
    match_result = get_path_match_from_chain(url, latest_version)
    return match_result.latest_path
