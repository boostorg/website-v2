import pytest
from unittest.mock import MagicMock, patch

from django.http import Http404
from django.http import HttpResponseNotFound
from django.test import RequestFactory
from django.urls import reverse

from core.views import StaticContentTemplateView


static_content_test_cases = [
    ("/develop/libs/index.html", 200, "text/html"),  # Example 1
    ("/develop/doc/index.html", 200, "text/html"),  # Example 2
    ("/index.html", 200, "text/html"),  # Example 3
    ("/nonexistent/index.html", 404, None),  # Non-existent content
    ("/develop/libs/nonexistent.html", 404, None),  # Non-existent content in libs
]


def mock_get_content_from_s3(key):
    mock_content = {
        "/site/develop/libs/index.html": ("libs content", "text/html"),
        "/site/develop/doc/html/index.html": ("doc content", "text/html"),
        "/site/develop/index.html": ("root content", "text/html"),
        "/site/index.html": ("site root content", "text/html"),
    }
    return mock_content.get(key, None)


@pytest.mark.django_db
@pytest.mark.parametrize("content_path, expected_status, expected_content_type", static_content_test_cases)
def test_static_content_template_view(content_path, expected_status, expected_content_type):
    factory = RequestFactory()
    view = StaticContentTemplateView.as_view()

    with patch('core.boostrenderer.get_content_from_s3', side_effect=mock_get_content_from_s3):
        request = factory.get(
            reverse("static-content-page", kwargs={"content_path": content_path})
        )
        try:
            response = view(request, content_path=content_path)
        except Http404:
            if expected_status == 404:
                assert True
            else:
                assert False, "Unexpected Http404"
        else:
            # Check if the response has the expected status code
            assert response.status_code == expected_status
            if expected_status == 200:
                # Check if the Content-Type header is present and matches the expected content type
                assert "Content-Type" in response.headers
                assert response.headers["Content-Type"] == expected_content_type
            else:
                # Check if the response is an Http404 error for non-existent content
                assert isinstance(response, HttpResponseNotFound)



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
