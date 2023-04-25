import pytest
import time
from unittest.mock import patch

from django.core.cache import caches
from django.test import RequestFactory
from django.test.utils import override_settings
from django.urls import reverse

from core.views import StaticContentTemplateView


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


# Define test cases with the paths based on the provided config file
static_content_test_cases = [
    "/develop/libs/rst.css",  # Test a site_path from the config file
    "/develop/doc/index.html",  # Test a site_path with a more complex substitution schema
    "/rst.css",  # Test a the default site_path from the config file
    "site/develop/doc/html/about.html",  # Test direct access to a file in the S3 bucket
]


def mock_get_content_from_s3(key=None, bucket_name=None):
    # Map the S3 paths to a sample content and content type
    content_mapping = {
        "/site/develop/libs/rst.css": (b"fake rst.css content", "text/css"),
        "/site/develop/doc/html/index.html": (b"fake index.html content", "text/html"),
        "/site/develop/rst.css": (b"fake rst.css content", "text/css"),
        "/site/develop/doc/html/about.html": (b"fake about.html content", "text/html"),
    }
    return content_mapping.get(key, None)


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
@pytest.mark.django_db
@pytest.mark.parametrize("content_path", static_content_test_cases)
@patch("core.views.get_content_from_s3", new=mock_get_content_from_s3)
def test_static_content_template_view(content_path):
    """
    Test the StaticContentTemplateView view"""
    request = RequestFactory().get(content_path)
    view = StaticContentTemplateView.as_view()
    response = view(request, content_path=content_path)

    # Get the mock content and content type for the content_path
    mock_content = mock_get_content_from_s3(content_path)

    if mock_content:
        # Check if the response has the expected status code and content type
        assert response.status_code == 200
        assert "Content-Type" in response.headers
        assert response.content == mock_content[0]
    else:
        # If the content doesn't exist, check if the response has a 404 status code
        assert response.status_code == 404


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
