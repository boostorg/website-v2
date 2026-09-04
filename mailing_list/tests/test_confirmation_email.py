"""The subscription confirmation email itself.

The view tests mock _send_confirmation_email away, so this is where the
rendered message is checked.
"""

import re

import pytest
from django.core import mail

from mailing_list.constants import MAILMAN_LISTS
from mailing_list.views import _send_confirmation_email

pytestmark = pytest.mark.django_db


def _send(rf):
    request = rf.get("/", HTTP_HOST="testserver")
    _send_confirmation_email(request, "subscriber@example.com", None, MAILMAN_LISTS[:2])
    return mail.outbox[0]


def test_confirmation_email_is_branded_multipart(rf):
    msg = _send(rf)

    assert msg.subject == "Confirm your Boost mailing list subscription"
    assert msg.recipients() == ["subscriber@example.com"]

    html_body = next(
        alt.content for alt in msg.alternatives if alt.mimetype == "text/html"
    )
    assert "Confirm your subscription" in html_body
    assert "Confirm my subscription" in html_body


def test_confirmation_link_is_absolute_and_in_both_bodies(rf):
    msg = _send(rf)
    html_body = next(
        alt.content for alt in msg.alternatives if alt.mimetype == "text/html"
    )

    confirm_urls = {
        href
        for href in re.findall(r'href="([^"]*)"', html_body)
        if "/mailing-list/confirm/" in href
    }
    assert len(confirm_urls) == 1
    confirm_url = confirm_urls.pop()
    assert confirm_url.startswith("http://testserver/")
    assert confirm_url in msg.body

    for href in re.findall(r'href="([^"]*)"', html_body):
        assert href.startswith(("http://", "https://", "mailto:")), href
