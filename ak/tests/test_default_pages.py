import pytest
import random


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


def test_404_page(db, logged_in_tp):
    """Test a 404 error page"""

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
