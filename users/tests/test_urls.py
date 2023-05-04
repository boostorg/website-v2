import pytest
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from test_plus import TestCase


User = get_user_model()


def test_login_url(client, db):
    """
    GET /accounts/login/

    Just a canary test that the login screen exists.
    """
    tp = TestCase()
    tp.client = client
    res = tp.get("account_login")
    tp.response_200(res)


def test_login_url_post(client, user):
    """
    POST /accounts/login/

    A user can log in
    """
    tp = TestCase()
    tp.client = client
    res = tp.post("account_login", data={"email": user.email, "password": "password"})
    tp.response_200(res)


def test_logout_url(client, db):
    """
    GET /accounts/logout/

    Just a canary test that the logout screen exists.
    """
    tp = TestCase()
    tp.client = client
    res = tp.get("account_login")
    tp.response_200(res)


def test_password_reset_url(client, db):
    """
    GET /accounts/password/reset/

    Just a canary test that the password reset screen exists.
    """
    tp = TestCase()
    tp.client = client
    res = tp.get("account_reset_password")
    tp.response_200(res)


def test_signup_200(client, db):
    """
    GET /accounts/signup/

    Just a canary test that the signup screen exists.
    """
    tp = TestCase()
    tp.client = client
    res = tp.get("account_signup")
    tp.response_200(res)


def test_signup_post(client, db):
    """
    POST /accounts/signup/

    A user can sign up
    """
    tp = TestCase()
    tp.client = client
    res = tp.post(
        "account_signup",
        data={
            "email": "testerson@example.com",
            "password1": "passw0rd!",
            "password2": "passw0rd!",
        },
    )
    tp.response_302(res)
    assert User.objects.filter(email="testerson@example.com").exists()


def test_profile_photo_auth(client, db):
    """
    POST /users/me/photo/

    Canary test that the photo upload page is protected.
    """
    tp = TestCase()
    tp.client = client
    res = tp.post("profile-photo")
    tp.response_302(res)
    assert "/accounts/login" in res.url


@override_settings(MEDIA_ROOT=tempfile.gettempdir())
def test_profile_photo_update_success(tp, user, client):
    """
    POST /users/me/photo

    Confirm that user can update their profile photo
    """
    old_image = user.image
    client.force_login(user)
    image = SimpleUploadedFile(
        "/image/fpo/user.png", b"file_content", content_type="image/png"
    )
    res = tp.post("profile-photo", data={"image": image})
    tp.response_302(res)
    assert f"/users/{user.pk}" in res.url
    user.refresh_from_db()
    assert user.image != old_image


@pytest.mark.skip(reason="Revisit once we have the profile implemented")
def test_profile_photo_github_auth(tp, db):
    """
    POST /users/me/update-github-photo/

    Canary test that the github photo update page is protected.
    """
    res = tp.post("profile-photo-github")
    tp.response_302(res)
    assert "/accounts/login" in res.url
