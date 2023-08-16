import random

import pytest
from django.test.utils import override_settings


def test_homepage(db, tp):
    """Ensure we can hit the homepage"""
    # Use any page that is named 'home' otherwise use /
    url = tp.reverse("home")
    if not url:
        url = "/"

    response = tp.get_check_200(url)
    # Check that "entries" is in the context
    assert "entries" in response.context


def test_homepage_beta(db, tp):
    """Ensure we can hit the beta homepage"""
    url = tp.reverse("home-beta")

    tp.get_check_200(url)


def test_homepage_beta_context(db, tp):
    """Ensure have the expected context data on the homepage"""
    # Use any page that is named 'home' otherwise use /
    url = tp.reverse("home-beta")
    response = tp.get_check_200(url)

    # Check that "entries" is in the context
    assert "entries" in response.context


def test_200_page(db, tp):
    """Test a 200 OK page"""

    response = tp.get("ok")
    tp.response_200(response)


def test_403_page(db, tp):
    """Test a 403 error page"""

    response = tp.get("forbidden")
    tp.response_403(response)


@override_settings(
    CACHES={
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
        "static_content": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "TIMEOUT": 86400,
        },
    }
)
def test_404_page(db, tp):
    """
    Test a 404 error page

    This test is a bit more complicated than the others because the
    this/should/not/exist URL will hit StaticContentTemplateView first
    to see if there is static content to serve, and cache it if so. To avoid
    errors in CI, we need to make sure that the cache is cleared before
    running this test.
    """

    rando = random.randint(1000, 20000)
    url = f"/this/should/not/exist/{rando}/"
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
