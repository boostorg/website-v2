import pytest
from unittest.mock import MagicMock, patch

from libraries.path_matcher import (
    BasePathMatcher,
    DirectMatcher,
    LibsPathToLatestDirectMatcher,
    LibsPathToLatestFallbackMatcher,
    LibsToAntoraPathDirectMatcher,
    DocHtmlBoostPathToFallbackMatcher,
    DocHtmlPathToDirectMatcher,
    DocHtmlBoostHtmlFallbackPathMatcher,
    ToLibsLatestRootFallbackMatcher,
)
from libraries.path_matcher.utils import get_path_match_from_chain, determine_latest_url

test_params = [
    (
        DirectMatcher,
        True,  # confirm_path_exists result
        False,  # confirm s3 path exists result
        "1_84_0/libs/algorithm/doc/html/algorithm/CXX11.html",  # src path
        "static_content_1_79_0/libs/algorithm/doc/html/algorithm/CXX11.html",  # expected s3 key
        True,  # is direct equivalent
        "doc/libs/latest/libs/algorithm/doc/html/algorithm/CXX11.html",  # expected final path
    ),
    (
        LibsPathToLatestDirectMatcher,
        True,  # confirm_path_exists result
        False,  # confirm s3 path exists result
        "1_84_0/libs/algorithm/doc/html/algorithm/CXX11.html",  # src path
        "static_content_1_79_0/libs/algorithm/doc/html/algorithm/CXX11.html",  # expected s3 key
        False,  # is not a direct equivalent
        "doc/libs/latest/libs/algorithm/doc/html/algorithm/CXX11.html",  # expected final path
    ),
    (
        LibsPathToLatestFallbackMatcher,
        False,  # confirm_path_exists result
        False,  # confirm s3 path exists result
        "1_78_0/libs/algorithm/doc/html/header/boost/algorithm/string_regex_hpp.html",  # src path
        "static_content_1_79_0/libs/algorithm/index.html",  # expected s3 key
        False,
        "doc/libs/latest/libs/algorithm/index.html",  # expected final path
    ),
    (
        LibsToAntoraPathDirectMatcher,
        True,  # confirm_path_exists result
        False,  # confirm s3 path exists result
        "1_85_0/libs/url/doc/html/url/urls/segments.html",  # src path
        "static_content_1_79_0/doc/antora/url/urls/segments.html",  # expected s3 key
        False,
        "doc/libs/latest/doc/antora/url/urls/segments.html",  # expected final path
    ),
    (
        DocHtmlBoostPathToFallbackMatcher,
        True,  # confirm_path_exists result
        False,  # confirm s3 path exists result
        "1_64_0/doc/html/boost_process/acknowledgements.html",  # src path
        "static_content_1_79_0/libs/process/index.html",  # expected s3 key
        False,
        "doc/libs/latest/libs/process/index.html",  # expected final path
    ),
    (
        DocHtmlPathToDirectMatcher,
        False,  # confirm_path_exists result
        True,  # confirm s3 path exists result
        "1_35_0/doc/html/interprocess.html",  # src path
        "static_content_1_79_0/doc/html/interprocess.html",  # expected s3 key
        False,
        "doc/libs/latest/doc/html/interprocess.html",  # expected final path
    ),
    (
        DocHtmlBoostHtmlFallbackPathMatcher,
        False,  # confirm_path_exists result
        True,  # confirm s3 path exists result
        "1_34_0/doc/html/boost_math.html",  # src path
        "static_content_1_79_0/libs/math/doc/html/index.html",  # expected s3 key
        False,
        "doc/libs/latest/libs/math/doc/html/index.html",  # expected final path
    ),
    (
        ToLibsLatestRootFallbackMatcher,
        False,
        False,
        "1_33_1/doc/html/BOOST_VARIANT_LIMIT_TYPES.html",
        "static_content_1_79_0/libs",
        False,
        "libraries/latest/",
    ),
]


@pytest.mark.parametrize(
    "matcher_class,db_path_result,s3_path_result,test_path,expected_s3_key,is_direct_equivalent,expected_final_path",
    test_params,
)
def test_libs_path_to_latest_exact_db_path_exists(
    matcher_class,
    db_path_result,
    s3_path_result,
    test_path,
    expected_s3_key,
    is_direct_equivalent,
    expected_final_path,
    monkeypatch,
    version,
):
    monkeypatch.setattr(
        BasePathMatcher, "confirm_db_path_exists", lambda x, y: db_path_result
    )
    monkeypatch.setattr(
        BasePathMatcher, "confirm_s3_path_exists", lambda x, y: s3_path_result
    )

    mock_s3_client = MagicMock()
    matcher = matcher_class(version, mock_s3_client)

    with patch.object(
        matcher, "confirm_db_path_exists", wraps=matcher.confirm_db_path_exists
    ) as spy:
        pm = matcher.determine_match(test_path)
        spy.assert_called_once_with(expected_s3_key)

    assert pm.is_direct_equivalent == is_direct_equivalent
    assert pm.latest_path == expected_final_path


chain_data = [
    (
        "1_84_0/libs/algorithm/doc/html/algorithm/CXX11.html",
        "doc/libs/latest/libs/algorithm/doc/html/algorithm/CXX11.html",
        True,
        DirectMatcher,
    ),
    (
        "1_84_0/libs/algorithm/doc/html/algorithm/CXX11.html",
        "doc/libs/latest/libs/algorithm/doc/html/algorithm/CXX11.html",
        True,
        LibsPathToLatestDirectMatcher,
    ),
    (
        "1_84_0/libs/algorithm/doc/html/algorithm/nope.html",
        "doc/libs/latest/libs/algorithm/index.html",
        False,
        LibsPathToLatestFallbackMatcher,
    ),
    (
        "1_85_0/libs/url/doc/html/url/urls/segments.html",
        "doc/libs/latest/doc/antora/url/urls/segments.html",
        True,
        LibsToAntoraPathDirectMatcher,
    ),
    (
        "1_35_0/doc/html/interprocess.html",
        "doc/libs/latest/doc/html/interprocess.html",
        True,
        DocHtmlPathToDirectMatcher,
    ),
    (
        "1_64_0/doc/html/boost_process/acknowledgements.html",
        "doc/libs/latest/libs/process/index.html",
        True,
        DocHtmlBoostPathToFallbackMatcher,
    ),
    (
        "1_34_0/doc/html/boost_math.html",
        "doc/libs/latest/libs/math/doc/html/index.html",
        False,
        DocHtmlBoostHtmlFallbackPathMatcher,
    ),
    (
        "1_XX_Y/does/not/exist",
        "libraries/latest/",
        False,
        ToLibsLatestRootFallbackMatcher,
    ),
]


@pytest.mark.parametrize(
    "test_url,expected_match,db_path_exists,matching_class", chain_data
)
def test_handoff(
    test_url, expected_match, db_path_exists, matching_class, monkeypatch, version
):
    # default deny
    monkeypatch.setattr(BasePathMatcher, "confirm_db_path_exists", lambda x, y: False)
    monkeypatch.setattr(BasePathMatcher, "confirm_s3_path_exists", lambda x, y: False)
    # Using match_class here because for the likes of the antora case we want to have it match on
    #  LibsToAntoraPathDirectMatcher specifically, not an earlier matching regex where the key would not be in db/s3.
    #  Same reason we use match_class(version, mock_s3_client).get_class_name() below rather than a string name for the class
    monkeypatch.setattr(
        matching_class, "confirm_db_path_exists", lambda x, y: db_path_exists
    )

    match_result = get_path_match_from_chain(test_url, latest_version=version)

    mock_s3_client = MagicMock()
    assert match_result.latest_path == expected_match
    assert (
        match_result.matcher == matching_class(version, mock_s3_client).get_class_name()
    )


def test_determine_latest_url(monkeypatch, version):
    monkeypatch.setattr(
        DocHtmlBoostHtmlFallbackPathMatcher, "confirm_db_path_exists", lambda x, y: True
    )

    test_url = "1_34_0/doc/html/boost_math.html"
    expected_latest_url = "doc/libs/latest/libs/math/doc/html/index.html"

    assert determine_latest_url(test_url, version) == expected_latest_url


def test_s3_archive_key_prefix(version):
    """Test that the S3 archive key correctly contains the 'archives/boost_' prefix"""
    mock_s3_client = MagicMock()

    test_path = "static_content_1_84_0/libs/algorithm/doc/html/algorithm/CXX11.html"
    expected_archive_key = (
        "archives/boost_1_84_0/libs/algorithm/doc/html/algorithm/CXX11.html"
    )

    # Create a matcher instance with the mock s3 client
    matcher = DirectMatcher(version, mock_s3_client)
    matcher.confirm_s3_path_exists(test_path)

    mock_s3_client.head_object.assert_called_once()
    call_kwargs = mock_s3_client.head_object.call_args[1]
    assert call_kwargs["Key"] == expected_archive_key
    assert call_kwargs["Key"].startswith("archives/")
    assert "archives/boost_" in call_kwargs["Key"]
