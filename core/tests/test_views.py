import pytest
import responses
import time

from django.core.cache import caches
from django.test import RequestFactory, TestCase
from django.test.utils import override_settings
from django.urls import reverse

from core.views import StaticContentTemplateView

from unittest.mock import patch
from django.core.cache import caches


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


@pytest.mark.django_db
@override_settings(
    CACHES={
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
        "machina_attachments": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache"
        },
        "static_content": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "TIMEOUT": 86400,
        },
    }
)
def test_cache_behavior(request_factory, content_path):
    """Tests the cache behavior of the StaticContentTemplateView view."""
    # Set up the mocked API call
    mock_content = "mocked content"
    mock_content_type = "text/plain"

    # Clear the cache before testing
    cache = caches["static_content"]
    cache.clear()

    with patch("core.views.get_content_from_s3") as mock_get_content_from_s3:
        mock_get_content_from_s3.return_value = (mock_content, mock_content_type)

        # Cache miss scenario
        response = call_view(request_factory, content_path)
        assert response.status_code == 200
        assert response.content.decode() == mock_content
        assert response["Content-Type"] == mock_content_type
        mock_get_content_from_s3.assert_called_once_with(key=content_path)

        # Cache hit scenario
        mock_get_content_from_s3.reset_mock()
        response = call_view(request_factory, content_path)
        assert response.status_code == 200
        assert response.content.decode() == mock_content
        assert response["Content-Type"] == mock_content_type
        mock_get_content_from_s3.assert_not_called()

        # Cache expiration scenario
        cache.set(
            "static_content_" + content_path, (mock_content, mock_content_type), 1
        )  # Set a 1-second cache timeout
        time.sleep(2)  # Wait for the cache to expire
        mock_get_content_from_s3.reset_mock()
        response = call_view(request_factory, content_path)
        assert response.status_code == 200
        assert response.content.decode() == mock_content
        assert response["Content-Type"] == mock_content_type
        mock_get_content_from_s3.assert_called_once_with(key=content_path)


static_content_test_cases = [
    "/site/develop/rst.css",
    "/marshmallow/index.html",
    "/marshmallow/any.html",
    "/rst.css",
    "doc/html/about.html",
    "site/develop/doc/html/about.html",
]


@pytest.mark.skip(reason="Hits the live S3 API")
@pytest.mark.django_db
@pytest.mark.parametrize("content_path", static_content_test_cases)
def test_static_content_template_view(content_path):
    """
    NOTE: This test hits the live S3 API and was used for debugging purposes. It is not
    intended to be run as part of the test suite.

    Test cases:
    - Direct reference to S3 file: "/site/develop/rst.css"
    - Reference via an alias in the config file: "/marshmallow/index.html"
    - Reference via a second instance of the same alias in the config file, not found in the first one: "/marshmallow/about.html"
    - Reference via the pass-through "/" alias to "/site/develop/": "/rst.css"
    - Reference via the pass-through "/" alias to a nested file: "/doc/html/about.html"
    """
    factory = RequestFactory()
    view = StaticContentTemplateView.as_view()

    request = factory.get(
        reverse("static-content-page", kwargs={"content_path": content_path})
    )
    response = view(request, content_path=content_path)

    # Check if the response has a status code of 200 (OK)
    assert response.status_code == 200
    # Check if the Content-Type header is present in the response
    assert "Content-Type" in response.headers


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
