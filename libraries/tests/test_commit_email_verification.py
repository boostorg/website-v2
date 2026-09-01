"""The commit-author claim confirmation email."""

import re

import pytest
from django.core import mail

from libraries.tasks import send_commit_author_email_verify_mail

CONFIRM_URL = "http://testserver/libraries/commit-author-email/verify/abc-123/"


@pytest.mark.django_db
def test_v3_verification_email_is_branded_multipart():
    send_commit_author_email_verify_mail(
        "author@example.com", CONFIRM_URL, requester="Vinnie Falco", v3=True
    )

    msg = mail.outbox[0]
    assert msg.subject == "Confirm your commit email address"
    assert msg.recipients() == ["author@example.com"]

    html_body = next(
        alt.content for alt in msg.alternatives if alt.mimetype == "text/html"
    )
    assert "Confirm your commit email" in html_body
    assert "Vinnie Falco has asked to link author@example.com" in html_body
    assert CONFIRM_URL in html_body
    assert CONFIRM_URL in msg.body

    for href in re.findall(r'href="([^"]*)"', html_body):
        assert href.startswith(("http://", "https://", "mailto:")), href


@pytest.mark.django_db
def test_v3_verification_email_without_a_named_requester():
    """The claimant's name is optional, and the copy must not leak their
    account email in its place."""
    send_commit_author_email_verify_mail(
        "author@example.com", CONFIRM_URL, requester="", v3=True
    )

    html_body = next(
        alt.content
        for alt in mail.outbox[0].alternatives
        if alt.mimetype == "text/html"
    )
    assert "A user has asked to link author@example.com" in html_body
