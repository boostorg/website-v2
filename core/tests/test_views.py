import pytest
from unittest.mock import patch

from django.test import RequestFactory
from django.urls import reverse

from core.boostrenderer import get_content_from_s3
from core.views import StaticContentTemplateView

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
        assert response["Content-Type"] == mock_content[1]
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
