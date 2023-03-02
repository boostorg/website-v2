import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings


def test_login_url(tp, db):
    """
    GET /accounts/login/

    Just a canary test that the login screen exists.
    """
    res = tp.get("account_login")
    tp.response_200(res)


def test_login_url_post(tp, user):
    """
    POST /accounts/login/

    A user can log in
    """
    res = tp.post("account_login", data={"email": user.email, "password": "password"})
    tp.response_200(res)


def test_logout_url(tp, db):
    """
    GET /accounts/logout/

    Just a canary test that the logout screen exists.
    """
    res = tp.get("account_login")
    tp.response_200(res)


def test_password_reset_url(tp, db):
    """
    GET /accounts/password/reset/

    Just a canary test that the password reset screen exists.
    """
    res = tp.get("account_reset_password")
    tp.response_200(res)


def test_profile_photo_auth(tp, db):
    """
    POST /users/me/photo/

    Canary test that the photo upload page is protected.
    """
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


def test_profile_photo_github_auth(tp, db):
    """
    POST /users/me/update-github-photo/

    Canary test that the github photo update page is protected.
    """
    res = tp.post("profile-photo-github")
    tp.response_302(res)
    assert "/accounts/login" in res.url
