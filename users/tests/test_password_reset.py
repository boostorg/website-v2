"""End-to-end tests for the V3 password reset flow.

Covers: requesting a reset (known and unknown emails), the branded emails,
token validation (valid, invalid), setting the new password (including the
common-password rejection), and the legacy (non-V3) flow.
"""

import re

import pytest
import waffle.testutils
from django.core.exceptions import ValidationError
from django.urls import reverse

from users.validators import CommonPasswordValidator

RESET_LINK_RE = re.compile(r"https?://[^\s]+/password/reset/key/[^\s]+")

NEW_PASSWORD = "korkly-blue-mantis7"


@pytest.fixture(autouse=True)
def _disable_account_rate_limits(settings):
    """Avoid 429s from allauth's per-email rate limit across test runs."""
    settings.ACCOUNT_RATE_LIMITS = False


def _request_reset(tp, email):
    return tp.post("v3-password-reset", data={"email": email})


def _follow_reset_link(tp, mailoutbox):
    """Extract the reset link from the email and follow its redirect.

    Returns the session-backed ".../<uidb36>-set-password/" URL the
    password form lives at.
    """
    link = RESET_LINK_RE.search(mailoutbox[0].body).group(0)
    path = link.split("://", 1)[1].split("/", 1)[1]
    res = tp.client.get(f"/{path}")
    assert res.status_code == 302
    return res["Location"]


@waffle.testutils.override_flag("v3", active=True)
def test_reset_request_sends_branded_email(tp, user, mailoutbox):
    """A reset request for a registered email sends the branded reset email
    linking into the V3 flow."""
    res = _request_reset(tp, user.email)

    assert res.status_code == 302
    assert res["Location"] == reverse("v3-password-reset-done")
    assert len(mailoutbox) == 1
    msg = mailoutbox[0]
    assert msg.to == [user.email]
    assert msg.subject == "Password reset link"
    assert "/v3/accounts/password/reset/key/" in msg.body
    # The branded HTML alternative carries the same reset link
    html = msg.alternatives[0][0]
    assert msg.alternatives[0][1] == "text/html"
    assert "/v3/accounts/password/reset/key/" in html
    assert "Reset your password" in html


@waffle.testutils.override_flag("v3", active=True)
def test_reset_request_unknown_email_sends_signup_email(tp, db, mailoutbox):
    """A reset request for an unregistered email sends the "no account
    found" email pointing at signup."""
    res = _request_reset(tp, "not-registered@example.com")

    # Same redirect as a known email, so accounts can't be enumerated
    assert res.status_code == 302
    assert res["Location"] == reverse("v3-password-reset-done")
    assert len(mailoutbox) == 1
    msg = mailoutbox[0]
    assert msg.to == ["not-registered@example.com"]
    assert msg.subject == "No account found for this email"
    assert reverse("v3-signup") in msg.body
    html = msg.alternatives[0][0]
    assert reverse("v3-signup") in html
    assert "no Boost account registered" in html


@waffle.testutils.override_flag("v3", active=True)
def test_reset_request_for_social_only_user_sends_email(tp, user, mailoutbox):
    """A user with no usable password (e.g. a social-only signup) can still
    request a reset to set one; the response and email match a normal account."""
    user.set_unusable_password()
    user.save()

    res = _request_reset(tp, user.email)

    assert res.status_code == 302
    assert res["Location"] == reverse("v3-password-reset-done")
    assert len(mailoutbox) == 1
    assert mailoutbox[0].subject == "Password reset link"


@waffle.testutils.override_flag("v3", active=True)
def test_reset_request_preserves_entered_email_on_error(tp, db):
    """A malformed email re-renders the form with the entered value seeded into
    both the input and the Alpine state, so it survives client-side hydration.

    The value is kept free of escapejs-special characters so the Alpine seed
    can be asserted literally.
    """
    res = tp.post("v3-password-reset", data={"email": "bademail"})

    assert res.status_code == 200
    content = res.content.decode()
    # Server-rendered input value (progressive enhancement / no JS).
    assert 'value="bademail"' in content
    # Alpine state seed — without it, x-model would wipe the field on init.
    assert "value: 'bademail'" in content


@waffle.testutils.override_flag("v3", active=True)
def test_reset_request_page_renders(tp, db):
    """GET on the reset request page renders the email form."""
    res = tp.get("v3-password-reset")

    assert res.status_code == 200
    content = res.content.decode()
    assert "Password reset" in content
    assert 'name="email"' in content


@waffle.testutils.override_flag("v3", active=True)
def test_reset_done_page_renders(tp, db):
    """GET on the reset-sent confirmation page renders."""
    res = tp.get("v3-password-reset-done")

    assert res.status_code == 200
    assert "We have sent you an e-mail" in res.content.decode()


@waffle.testutils.override_flag("v3", active=True)
def test_reset_link_shows_change_password_form(tp, user, mailoutbox):
    """Following a valid reset link lands on the change password form."""
    _request_reset(tp, user.email)
    form_url = _follow_reset_link(tp, mailoutbox)

    assert form_url.endswith("-set-password/")
    res = tp.client.get(form_url)
    assert res.status_code == 200
    content = res.content.decode()
    assert "Change Password" in content
    assert 'name="password1"' in content


@waffle.testutils.override_flag("v3", active=True)
def test_invalid_reset_link_shows_error_state(tp, db):
    """A tampered or expired reset link shows the error state with a
    prompt to request a new link."""
    res = tp.get("v3-password-reset-from-key", uidb36="1a", key="bogus-token")

    assert res.status_code == 200
    content = res.content.decode()
    assert "Invalid reset link" in content
    assert "Request a new reset link" in content
    assert reverse("v3-password-reset") in content


@waffle.testutils.override_flag("v3", active=True)
def test_expired_reset_link_shows_error_state(tp, user, mailoutbox, settings):
    """A reset link older than PASSWORD_RESET_TIMEOUT shows the error state.

    Setting the timeout negative makes the freshly minted token already
    expired, so we exercise the expiry path without waiting an hour.
    """
    _request_reset(tp, user.email)
    link = RESET_LINK_RE.search(mailoutbox[0].body).group(0)
    path = "/" + link.split("://", 1)[1].split("/", 1)[1]

    settings.PASSWORD_RESET_TIMEOUT = -1
    res = tp.client.get(path)

    assert res.status_code == 200
    assert "Invalid reset link" in res.content.decode()


@waffle.testutils.override_flag("v3", active=True)
def test_common_password_is_rejected_with_inline_message(tp, user, mailoutbox):
    """Submitting a commonly used password re-renders the form with the
    inline error message."""
    _request_reset(tp, user.email)
    form_url = _follow_reset_link(tp, mailoutbox)

    res = tp.client.post(
        form_url, data={"password1": "password123", "password2": "password123"}
    )

    assert res.status_code == 200
    assert (
        "This password is too common. Please choose a different one."
        in res.content.decode()
    )
    user.refresh_from_db()
    assert not user.check_password("password123")


@waffle.testutils.override_flag("v3", active=True)
def test_mismatched_passwords_are_rejected(tp, user, mailoutbox):
    """Submitting two different passwords keeps the old password."""
    _request_reset(tp, user.email)
    form_url = _follow_reset_link(tp, mailoutbox)

    res = tp.client.post(
        form_url, data={"password1": NEW_PASSWORD, "password2": NEW_PASSWORD + "x"}
    )

    assert res.status_code == 200
    user.refresh_from_db()
    assert not user.check_password(NEW_PASSWORD)


@waffle.testutils.override_flag("v3", active=True)
def test_successful_reset_updates_password_and_claims_user(tp, user, mailoutbox):
    """A valid submission changes the password, claims the user, and lands
    on the confirmation page."""
    user.claimed = False
    user.save()
    _request_reset(tp, user.email)
    form_url = _follow_reset_link(tp, mailoutbox)

    res = tp.client.post(
        form_url, data={"password1": NEW_PASSWORD, "password2": NEW_PASSWORD}
    )

    assert res.status_code == 302
    assert res["Location"] == reverse("v3-password-reset-from-key-done")
    user.refresh_from_db()
    assert user.check_password(NEW_PASSWORD)
    assert user.claimed

    done = tp.client.get(res["Location"])
    assert "Your password is now changed" in done.content.decode()


@waffle.testutils.override_flag("v3", active=True)
def test_used_reset_link_shows_error_state(tp, user, mailoutbox):
    """The token is single-use: it dies with the password change."""
    _request_reset(tp, user.email)
    link = RESET_LINK_RE.search(mailoutbox[0].body).group(0)
    path = "/" + link.split("://", 1)[1].split("/", 1)[1]
    form_url = tp.client.get(path)["Location"]
    tp.client.post(
        form_url, data={"password1": NEW_PASSWORD, "password2": NEW_PASSWORD}
    )

    res = tp.client.get(path)

    assert res.status_code == 200
    assert "Invalid reset link" in res.content.decode()


@waffle.testutils.override_flag("v3", active=False)
def test_legacy_reset_email_links_to_legacy_route(tp, user, mailoutbox):
    """With the v3 flag off, the reset email links to the legacy flow."""
    res = tp.client.post(reverse("account_reset_password"), data={"email": user.email})

    assert res.status_code == 302
    assert len(mailoutbox) == 1
    body = mailoutbox[0].body
    assert "/accounts/password/reset/key/" in body
    assert "/v3/" not in body


def test_common_password_validator_message():
    """The common-password validator raises the actionable error message."""
    with pytest.raises(ValidationError) as excinfo:
        CommonPasswordValidator().validate("password123")
    assert excinfo.value.messages == [
        "This password is too common. Please choose a different one."
    ]
