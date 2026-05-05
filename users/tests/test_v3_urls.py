import waffle.testutils


@waffle.testutils.override_flag("v3", active=False)
def test_v3_password_reset_url_404_when_flag_off(tp, db):
    """
    GET /v3/accounts/password/reset/ with the v3 flag off returns 404.

    Verifies V3AuthContextMixin.dispatch gates the page behind the flag.
    """
    res = tp.get("v3-password-reset")
    tp.response_404(res)


@waffle.testutils.override_flag("v3", active=False)
def test_v3_password_reset_done_url_404_when_flag_off(tp, db):
    """
    GET /v3/accounts/password/reset/done/ with the v3 flag off returns 404.
    """
    res = tp.get("v3-password-reset-done")
    tp.response_404(res)


@waffle.testutils.override_flag("v3", active=False)
def test_v3_password_reset_from_key_url_404_when_flag_off(tp, db):
    """
    GET /v3/accounts/password/reset/key/ with the v3 flag off returns 404.
    """
    res = tp.get("v3-password-reset-from-key")
    tp.response_404(res)


@waffle.testutils.override_flag("v3", active=False)
def test_v3_password_reset_from_key_done_url_404_when_flag_off(tp, db):
    """
    GET /v3/accounts/password/reset/key/done/ with the v3 flag off returns 404.
    """
    res = tp.get("v3-password-reset-from-key-done")
    tp.response_404(res)
