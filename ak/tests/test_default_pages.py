import pytest
import random
from unittest.mock import MagicMock, patch

from django.http import Http404

from core.views import StaticContentTemplateView


def test_homepage(db, tp):
    """Ensure we can hit the homepage"""
    # Use any page that is named 'home' otherwise use /
    url = tp.reverse("home")
    if not url:
        url = "/"

    response = tp.get(url)
    tp.response_200(response)


def test_200_page(db, tp):
    """Test a 200 OK page"""

    response = tp.get("ok")
    tp.response_200(response)


def test_403_page(db, tp):
    """Test a 403 error page"""

    response = tp.get("forbidden")
    tp.response_403(response)


def test_404_page(db, tp):
    """Test a 404 error page"""

    rando = random.randint(1000, 20000)
    url = f"/this/should/not/exist/{rando}/"

    # Patch the get_content_from_s3 method for the StaticContentTemplateView class
    with patch.object(StaticContentTemplateView, "get", autospec=True) as mock_get:
        mock_get.side_effect = Http404("Page not found")

        response = tp.get(url)
        tp.response_404(response)

    response = tp.get("not_found")
    tp.response_404(response)


def test_500_page(db, tp):
    """Test our 500 error page"""

    url = tp.reverse("internal_server_error")

    # Bail out of this test if this view is not defined
    if not url:
        pytest.skip()

    with pytest.raises(ValueError):
        response = tp.get("internal_server_error")
        print(response.status_code)
