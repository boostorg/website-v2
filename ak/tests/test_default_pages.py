import pytest
import random

from django.test.utils import override_settings


def test_homepage(db, tp, logged_in_tp):
    """Ensure we can hit the homepage"""
    # Use any page that is named 'home' otherwise use /
    url = tp.reverse("home")
    if not url:
        url = "/"

    response = logged_in_tp.get(url)
    logged_in_tp.response_200(response)


def test_200_page(db, logged_in_tp):
    """Test a 200 OK page"""

    response = logged_in_tp.get("ok")
    logged_in_tp.response_200(response)


def test_403_page(db, logged_in_tp):
    """Test a 403 error page"""

    response = logged_in_tp.get("forbidden")
    logged_in_tp.response_403(response)


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
def test_404_page(db, logged_in_tp):
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
    response = logged_in_tp.get(url)
    logged_in_tp.response_404(response)

    response = logged_in_tp.get("not_found")
    logged_in_tp.response_404(response)


def test_500_page(db, logged_in_tp):
    """Test our 500 error page"""

    url = logged_in_tp.reverse("internal_server_error")

    # Bail out of this test if this view is not defined
    if not url:
        pytest.skip()

    with pytest.raises(ValueError):
        response = logged_in_tp.get("internal_server_error")
        logged_in_tp.response_500(response)
