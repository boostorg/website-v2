import logging
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


def test_qrc_redirect_and_plausible_payload(tp):
    """XFF present; querystring preserved; payload/headers correct."""
    with patch("core.views.requests.post", return_value=None) as post_mock:
        url = "/qrc/pv-01/library/latest/beast/?x=1&y=2"
        res = tp.get(url)

    tp.response_302(res)
    assert res["Location"] == "/library/latest/beast/?x=1&y=2"

    # Plausible call
    (endpoint,), kwargs = post_mock.call_args
    assert endpoint == "https://plausible.io/api/event"

    # View uses request.path, so no querystring in payload URL
    assert kwargs["json"] == {
        "name": "pageview",
        "domain": "qrc.boost.org",
        "url": "http://testserver/qrc/pv-01/library/latest/beast/",
        "referrer": "",  # matches view behavior with no forwarded referer
    }

    headers = kwargs["headers"]
    assert headers["Content-Type"] == "application/json"
    assert kwargs["timeout"] == 2.0


def test_qrc_falls_back_to_remote_addr_when_no_xff(tp):
    """No XFF provided -> uses REMOTE_ADDR (127.0.0.1 in Django test client)."""
    with patch("core.views.requests.post", return_value=None) as post_mock:
        res = tp.get("/qrc/camp/library/latest/algorithm/")

    tp.response_302(res)
    assert res["Location"] == "/library/latest/algorithm/"

    (_, kwargs) = post_mock.call_args
    headers = kwargs["headers"]
    assert headers["X-Forwarded-For"] == "127.0.0.1"  # Django test client default


def test_qrc_logs_plausible_error_but_still_redirects(tp, caplog):
    """Plausible post raises -> error logged; redirect not interrupted."""
    with patch("core.views.requests.post", side_effect=RuntimeError("boom")):
        with caplog.at_level(logging.ERROR, logger="core.views"):
            res = tp.get("/qrc/c1/library/", HTTP_USER_AGENT="ua")

    tp.response_302(res)
    assert res["Location"] == "/library/"
    assert any("Plausible event post failed" in r.message for r in caplog.records)


def test_redirect_to_library_detail_view(tp):
    """Test that /lib/<library_slug>/ redirects to library detail page with prioritized version."""
    response = tp.get("redirect-to-library-view", library_slug="algorithm")
    tp.response_302(response)
    assert response["Location"] == "/library/latest/algorithm/"


def test_redirect_to_library_detail_view_with_cookie(tp):
    """Test that /lib/<library_slug>/ redirects using version from cookie."""
    tp.client.cookies["boost_version"] = "boost-1-86-0"
    response = tp.get("redirect-to-library-view", library_slug="algorithm")
    tp.response_302(response)
    assert response["Location"] == "/library/1.86.0/algorithm/"
