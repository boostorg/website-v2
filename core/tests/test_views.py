from unittest.mock import patch

import pytest
from django.core.cache import caches
from django.test import RequestFactory
from django.test.utils import override_settings
from django.http import Http404

from core.views import StaticContentTemplateView

TEST_CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
    "static_content": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "TIMEOUT": 86400,
    },
}


@pytest.fixture
def cache_url(tp):
    """Returns a sample cache url."""
    url = tp.reverse("clear-cache")
    return f"{url}?content_type=foo"


@pytest.fixture
def request_factory():
    """Returns a RequestFactory instance."""
    return RequestFactory()


@pytest.fixture
def content_path():
    """Returns a sample content path."""
    return "/some/content/path"


def call_view(request_factory, content_path):
    """Calls the view with the given request_factory and content path."""
    request = request_factory.get(content_path)
    view = StaticContentTemplateView.as_view()
    response = view(request, content_path=content_path)
    return response


@pytest.fixture(autouse=True)
def clear_cache():
    """Clears the static content cache before each test case."""
    cache = caches["static_content"]
    cache.clear()


@pytest.mark.django_db
@override_settings(
    CACHES=TEST_CACHES,
)
def test_content_found(request_factory):
    """Test that content is found and returned."""
    content_path = "/develop/libs/rst.css"
    with patch(
        "core.views.get_content_from_s3",
        return_value={"content": b"fake content", "content_type": "text/plain"},
    ):
        response = call_view(request_factory, content_path)
    assert response.status_code == 200
    assert response.content == b"fake content"
    assert response["Content-Type"] == "text/plain"


@pytest.mark.django_db
@override_settings(
    CACHES=TEST_CACHES,
)
def test_content_not_found(tp, request_factory):
    """Test that a 404 response is returned for nonexistent content."""
    content_path = "/nonexistent/file.html"

    with patch("core.views.get_content_from_s3", side_effect=Http404):
        with pytest.raises(Http404):
            call_view(request_factory, content_path)


@pytest.mark.django_db
@override_settings(
    CACHES=TEST_CACHES,
)
def test_cache_expiration(request_factory):
    """Test that the cache expires after the specified timeout."""
    content_path = "/develop/doc/index.html"
    mock_content = b"fake content"
    mock_content_type = "text/html"
    cache = caches["static_content"]
    cache_key = f"static_content_{content_path}"

    # Set the content in the cache with a 1-second timeout
    cache.set(
        cache_key,
        {"content": mock_content, "content_type": mock_content_type},
        timeout=1,
    )


def test_clear_cache_view_anonymous_user(tp, cache_url):
    """Test that only staff users can access the clear cache view."""
    # Anonymous users should be redirected to the login page
    res = tp.get(cache_url)
    tp.response_403(res)


def test_clear_cache_regular_user(tp, user, cache_url):
    """Test that only staff users can access the clear cache view."""
    tp.login(user)
    res = tp.get(cache_url)
    tp.response_403(res)


def test_clear_cache_staff_user(tp, staff_user, cache_url):
    # Staff users should be able to access the view
    tp.login(staff_user)
    res = tp.get(cache_url)
    tp.response_200(res)


def test_clear_cache_missing_params(tp, staff_user):
    url = tp.reverse("clear-cache")
    tp.login(staff_user)
    res = tp.get(url)
    tp.response_404(res)


def test_clear_cache_by_cache_key(tp, staff_user):
    url = tp.reverse("clear-cache")
    url = f"{url}?cache_key=foo"
    tp.login(staff_user)
    res = tp.get(url)
    tp.response_200(res)


def test_markdown_view_top_level(tp):
    """GET /content/map"""
    res = tp.get("/markdown/foo")
    tp.response_200(res)


def test_markdown_view_trailing_slash(tp):
    res = tp.get("/markdown/foo/")
    tp.response_200(res)


def test_doc_libs_get_content_with_db_cache(request_factory):
    """Test DocLibsTemplateView.get_content with database caching enabled."""
    from core.views import DocLibsTemplateView

    # Mock S3 returning content
    mock_s3_result = {
        "content": b"<html>Test content</html>",
        "content_type": "text/html",
    }

    with patch("core.views.ENABLE_DB_CACHE", True), patch(
        "core.views.DocLibsTemplateView.get_from_database", return_value=None
    ) as mock_get_from_db, patch(
        "core.views.DocLibsTemplateView.get_from_s3", return_value=mock_s3_result
    ) as mock_get_from_s3, patch(
        "core.views.DocLibsTemplateView.save_to_database"
    ) as mock_save_to_db:

        view = DocLibsTemplateView()
        view.request = request_factory.get("/doc/libs/test/")
        result = view.get_content("test/path")

        # verify database was checked first
        mock_get_from_db.assert_called_once_with("static_content_test/path")
        # verify S3 was called after cache miss
        mock_get_from_s3.assert_called_once_with("test/path")
        # verify content was saved to database
        mock_save_to_db.assert_called_once_with(
            "static_content_test/path", mock_s3_result
        )

        assert result["content"] == mock_s3_result["content"]
        assert result["content_type"] == mock_s3_result["content_type"]
        assert "redirect" in result


def test_doc_libs_get_content_without_db_cache(request_factory):
    """Test DocLibsTemplateView.get_content with database caching disabled."""
    from core.views import DocLibsTemplateView

    # Mock S3 returning content
    mock_s3_result = {
        "content": b"<html>Test content</html>",
        "content_type": "text/html",
    }

    with patch("core.views.ENABLE_DB_CACHE", False), patch(
        "core.views.DocLibsTemplateView.get_from_s3", return_value=mock_s3_result
    ) as mock_get_from_s3:

        view = DocLibsTemplateView()
        view.request = request_factory.get("/doc/libs/test/")
        result = view.get_content("test/path")

        # verify S3 was called directly
        mock_get_from_s3.assert_called_once_with("test/path")

        assert result["content"] == mock_s3_result["content"]
        assert result["content_type"] == mock_s3_result["content_type"]
        assert "redirect" in result


@patch("core.views.DocLibsTemplateView.get_from_s3")
def test_doc_libs_get_content_not_found(mock_get_from_s3, request_factory):
    """Test DocLibsTemplateView.get_content when content is not found."""
    from core.views import DocLibsTemplateView, ContentNotFoundException

    # mock S3 returning None (content not found)
    mock_get_from_s3.return_value = None

    request = request_factory.get("/doc/libs/test/")
    view = DocLibsTemplateView()
    view.request = request

    with pytest.raises(ContentNotFoundException, match="Content not found"):
        view.get_content("nonexistent/path")


def test_markdown_view_top_level_includes_extension(tp):
    res = tp.get("/markdown/foo.html")
    tp.response_200(res)


def test_markdown_view_nested(tp):
    res = tp.get("/markdown/more_content/bar")
    tp.response_200(res)


def test_markdown_view_nested_trailing_slash(tp):
    res = tp.get("/markdown/more_content/bar/")
    tp.response_200(res)


def test_markdown_view_nested_includes_extenstion(tp):
    res = tp.get("/markdown/more_content/bar.md")
    tp.response_200(res)


def test_markdown_view_nested_index_direct_path(tp):
    res = tp.get("/markdown/more_content/index.html")
    tp.response_200(res)


def test_markdown_view_nested_should_load_an_index(tp):
    res = tp.get("/markdown/more_content")
    tp.response_200(res)


def test_markdown_view_nested_three_levels(tp):
    res = tp.get("/markdown/more_content/even_more_content/sample")
    tp.response_200(res)


def test_privacy_policy(db, tp):
    """Test the privacy policy view"""
    response = tp.get("privacy")
    tp.response_200(response)


def test_terms_of_use(db, tp):
    """Test the terms of use view"""
    response = tp.get("terms-of-use")
    tp.response_200(response)


def test_docs_libs_gateway_404(tp, mock_get_file_data):
    mock_get_file_data("<html></html>", "a-url")

    response = tp.get("docs-libs-page", content_path="other-url")
    # tp.response_404(response)
    tp.response_302(response)


@pytest.mark.skip(reason="Redirects broke these tests.")
def test_docs_libs_gateway_200_non_html(tp, mock_get_file_data):
    s3_content = b"Content does not matter"
    mock_get_file_data(s3_content, "foo", content_type="test/html")

    response = tp.get("docs-libs-page", content_path="foo")

    tp.response_200(response)
    assert response.content == s3_content


def test_doc_libs_version_redirect(tp):
    response = tp.get("redirect-to-library-page", requested_version="1.82.0")
    tp.response_302(response)
    assert response["Location"] == "/libraries/1.82.0/grid/"

    response = tp.get("redirect-to-library-page", requested_version="release")
    tp.response_302(response)
    assert response["Location"] == "/libraries/"


@pytest.mark.skip(reason="Currently not using iframes for libs docs.")
def test_docs_libs_gateway_200_lib_number_iframe(
    tp, mock_get_file_data, mock_get_leaf_data
):
    mock_get_file_data(mock_get_leaf_data, "boost_1_50_0/algorithm")
    response = tp.get("docs-libs-page", content_path="1_50_0/algorithm")
    tp.response_200(response)
    # check that the response contains the expected iframe
    assert b"docsiframe" in response.content
    assert b"spirit-nav" not in response.content


@pytest.mark.skip(reason="We're testing all docs showing in iframes")
def test_docs_libs_gateway_200_lib_number_no_iframe(
    tp, mock_get_file_data, mock_get_accumulators_data
):
    mock_get_file_data(mock_get_accumulators_data, "boost_1_86_0/algorithm")
    response = tp.get("docs-libs-page", content_path="1_86_0/algorithm")
    tp.response_200(response)
    assert b"docsiframe" not in response.content
    assert b"spirit-nav" in response.content


@pytest.mark.skip(reason="Redirects broke these tests.")
def test_docs_libs_gateway_200_html_transformed(rf, tp, mock_get_file_data):
    s3_content = b"""
    <html>
    <head><title>My Page</title></head>
    <body><p>Something interesting.</p></body>
    </html>
    """
    mock_get_file_data(s3_content, "foo")

    response = tp.get("docs-libs-page", content_path="foo")

    # tp.response_200(response)
    tp.response_302(response)
    tp.assertResponseContains("<title>My Page</title>", response)

    # The modern head is inserted in the legacy page
    tp.assertResponseNotContains('<div id="boost-legacy-docs-header">', response)

    # XXX: The modern body is not being inserted in the legacy pages
    legacy_body = """
    <div id="boost-legacy-docs-body">
      <p>Something interesting.</p>
    </div>
    """
    tp.assertResponseNotContains(legacy_body, response)


def test_calendar(rf, tp):
    response = tp.get("calendar")
    tp.response_200(response)


@pytest.mark.django_db
@override_settings(
    CACHES=TEST_CACHES,
)
def test_static_content_blocks_direct_doc_paths(request_factory):
    """Test that direct access to doc paths and library paths is blocked with 404."""

    # Test cases for paths that should be blocked (return 404)
    blocked_paths = [
        # Original doc/html paths that should be blocked
        "boost_1_53_0_beta1/doc/html/index.html",
        "1_82_0/doc/html/tutorial.html",
        "1_55_0b1/doc/html/reference/api.html",
        "boost_1_86_0/doc/html/deep/nested/path.html",
        "1_75_0/doc/html/simple.html",
        # Edge cases with different boost version formats
        "boost_1_53_0_beta1/doc/html/",  # trailing slash
        "1_82_0/doc/html/a",  # single character file
        # NEW: Library paths that should now be blocked
        "boost_1_53_0_beta1/libs/algorithm/doc/index.html",
        "1_82_0/libs/filesystem/doc/index.html",
        "boost_1_86_0/libs/test/doc/reference.html",
        "1_75_0/libs/wave/doc/tutorial.html",
        "boost_1_82_0/libs/any_library/any_file.html",
        "1_55_0b1/libs/serialization/index.html",
        # Edge cases for libs paths
        "boost_1_53_0_beta1/libs/",  # just libs with trailing slash
        "1_82_0/libs/a",  # single character lib name
    ]

    for content_path in blocked_paths:
        request = request_factory.get(f"/{content_path}")
        view = StaticContentTemplateView.as_view()

        # Should raise Http404 without even trying to fetch from S3
        with pytest.raises(Http404):
            view(request, content_path=content_path)


@pytest.mark.django_db
@override_settings(
    CACHES=TEST_CACHES,
)
def test_static_content_allows_non_direct_doc_paths(request_factory):
    """Test that non-direct doc paths are allowed and processed normally."""

    # Test cases for paths that should NOT be blocked (normal processing)
    allowed_paths = [
        # Tools paths - should still be allowed (not libs)
        "1_82_0/tools/build/doc/index.html",
        "boost_1_82_0/tools/cmake/doc/reference.html",
        # Paths with non-boost-version prefixes - should be allowed
        "develop/libs/filesystem/doc/index.html",  # develop prefix, not version
        "master/libs/test/doc/reference.html",  # master prefix, not version
        # Paths without version prefixes
        "doc/html/index.html",  # No boost version prefix
        "some/other/doc/html/file.html",  # Different structure
        "libs/algorithm/doc/index.html",  # No version prefix
        # Paths that don't match the exact patterns
        "boost_1_82_0/doc/other/file.html",  # not /doc/html/
        "1_82_0/doc/htmls/file.html",  # not exact /doc/html/
        "1_82_0/documentation/html/file.html",  # not /doc/html/
        "boost_1_82_0/libraries/algorithm/doc/index.html",  # libraries not libs
        "some_other_prefix/libs/algorithm/doc/index.html",  # no boost version
    ]

    for content_path in allowed_paths:
        # Mock S3 to return content so we can test the path isn't blocked
        with patch(
            "core.views.get_content_from_s3",
            return_value={"content": b"test content", "content_type": "text/plain"},
        ):
            response = call_view(request_factory, content_path)
            # Should get 200 response, not 404 - the main thing is it's not blocked
            assert (
                response.status_code == 200
            ), f"Path should be allowed but got {response.status_code}: {content_path}"


def test_boost_version_regex_doc_html_pattern():
    """Test the BOOST_VERSION_REGEX doc/html pattern matches expected version formats."""
    import re
    from core.constants import BOOST_VERSION_REGEX

    # Test the doc/html blocking pattern used in the view
    doc_html_pattern = rf"^{BOOST_VERSION_REGEX}/doc/html/.+$"

    # Test cases that should match the doc/html pattern
    matching_cases = [
        "boost_1_53_0_beta1/doc/html/index.html",
        "1_82_0/doc/html/tutorial.html",
        "1_55_0b1/doc/html/reference/api.html",
        "boost_1_86_0/doc/html/test.html",
        "1_75_0/doc/html/simple.html",
    ]

    for test_path in matching_cases:
        match = re.match(doc_html_pattern, test_path)
        assert match is not None, f"Doc/html pattern should match: {test_path}"
        # The captured groups should match the expected version parts
        version_match = re.match(BOOST_VERSION_REGEX, test_path)
        assert version_match is not None, f"Version pattern should match: {test_path}"

    # Test cases that should NOT match the doc/html pattern
    non_matching_cases = [
        "1_82_0/tools/build/doc/index.html",  # tools path
        "develop/doc/html/index.html",  # develop prefix, not version
        "doc/html/index.html",  # no version prefix
        "boost_1_82_0/doc/other/file.html",  # not /doc/html/
        "1_82_0/doc/htmls/file.html",  # not exact /doc/html/
        "some/other/doc/html/file.html",  # no boost version
        "boost_1_82_0/doc/html/",  # no file after /doc/html/
        "1_82_0/doc/html",  # no trailing slash or file
        "boost_1_53_0_beta1/libs/algorithm/doc/index.html",  # libs path
    ]

    for test_path in non_matching_cases:
        match = re.match(doc_html_pattern, test_path)
        assert match is None, f"Doc/html pattern should NOT match: {test_path}"


def test_boost_version_regex_libs_pattern():
    """Test the BOOST_VERSION_REGEX libs pattern matches expected version formats."""
    import re
    from core.constants import BOOST_VERSION_REGEX

    # Test the libs blocking pattern used in the view
    libs_pattern = rf"^{BOOST_VERSION_REGEX}/libs/.+$"

    # Test cases that should match the libs pattern
    matching_cases = [
        "boost_1_53_0_beta1/libs/algorithm/doc/index.html",
        "1_82_0/libs/filesystem/doc/index.html",
        "boost_1_86_0/libs/test/doc/reference.html",
        "1_75_0/libs/wave/doc/tutorial.html",
        "boost_1_82_0/libs/any_library/any_file.html",
        "1_55_0b1/libs/serialization/index.html",
        "1_82_0/libs/a",  # single character lib name
        "boost_1_53_0_beta1/libs/algorithm",  # no trailing file extension
    ]

    for test_path in matching_cases:
        match = re.match(libs_pattern, test_path)
        assert match is not None, f"Libs pattern should match: {test_path}"
        # The captured groups should match the expected version parts
        version_match = re.match(BOOST_VERSION_REGEX, test_path)
        assert version_match is not None, f"Version pattern should match: {test_path}"

    # Test cases that should NOT match the libs pattern
    non_matching_cases = [
        "1_82_0/tools/build/doc/index.html",  # tools path
        "develop/libs/filesystem/doc/index.html",  # develop prefix, not version
        "latest/libs/algorithm/doc/index.html",  # latest prefix, not version
        "libs/algorithm/doc/index.html",  # no version prefix
        "boost_1_82_0/libraries/algorithm/doc/index.html",  # libraries not libs
        "some/other/libs/algorithm/file.html",  # no boost version
        "boost_1_82_0/libs",  # no trailing slash or file
        "boost_1_53_0_beta1/libs/",  # just libs with trailing slash (no content after)
        "1_82_0/doc/html/index.html",  # doc/html path
    ]

    for test_path in non_matching_cases:
        match = re.match(libs_pattern, test_path)
        assert match is None, f"Libs pattern should NOT match: {test_path}"
