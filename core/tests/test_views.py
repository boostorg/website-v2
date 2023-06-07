import pytest
from unittest.mock import patch

from django.core.cache import caches
from django.test import RequestFactory
from django.test.utils import override_settings

from core.views import StaticContentTemplateView


TEST_CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
    "machina_attachments": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
    "static_content": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "TIMEOUT": 86400,
    },
}


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
def test_content_not_found(request_factory):
    """Test that a 404 response is returned for nonexistent content."""
    content_path = "/nonexistent/file.html"
    with patch("core.views.get_content_from_s3", return_value=None):
        response = call_view(request_factory, content_path)
    assert response.status_code == 404


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
