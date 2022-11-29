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
