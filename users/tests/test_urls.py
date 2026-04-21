import waffle.testutils
from django.contrib.auth import get_user_model


User = get_user_model()


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


@waffle.testutils.override_flag("v3", active=True)
def test_v3_password_reset_url(tp, db):
    """
    GET /v3/accounts/password/reset/

    Canary test that the V3 password reset entry page renders.
    """
    res = tp.get("v3-password-reset")
    tp.response_200(res)


@waffle.testutils.override_flag("v3", active=True)
def test_v3_password_reset_done_url(tp, db):
    """
    GET /v3/accounts/password/reset/done/

    Canary test that the V3 password reset confirmation page renders.
    """
    res = tp.get("v3-password-reset-done")
    tp.response_200(res)


@waffle.testutils.override_flag("v3", active=True)
def test_v3_password_reset_from_key_url(tp, db):
    """
    GET /v3/accounts/password/reset/key/

    Canary test that the V3 change password page renders.
    """
    res = tp.get("v3-password-reset-from-key")
    tp.response_200(res)


@waffle.testutils.override_flag("v3", active=True)
def test_v3_password_reset_from_key_done_url(tp, db):
    """
    GET /v3/accounts/password/reset/key/done/

    Canary test that the V3 password changed confirmation page renders.
    """
    res = tp.get("v3-password-reset-from-key-done")
    tp.response_200(res)


def test_signup_200(tp, db):
    """
    GET /accounts/signup/

    Just a canary test that the signup screen exists.
    """
    res = tp.get("account_signup")
    tp.response_200(res)


def test_signup_post(tp, db):
    """
    POST /accounts/signup/

    A user can sign up
    """
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
