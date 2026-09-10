"""The post-published email, sent from pages.signals via a Celery task."""

import re

import pytest
from django.core import mail
from model_bakery import baker

from pages.tasks import send_post_published_email


@pytest.mark.django_db
def test_post_published_email_is_branded_multipart(user, wagtail_site, make_post_page):
    page = make_post_page(
        title="Boost 1.90.0 has been released",
        owner=user,
        summary="A summary of the release.",
    )

    send_post_published_email(page.pk)

    msg = mail.outbox[0]
    assert msg.subject == "Boost.org: Your post is live"
    assert msg.recipients() == [user.email]

    html_body = next(
        alt.content for alt in msg.alternatives if alt.mimetype == "text/html"
    )
    assert f"Hi {user.display_name}" in html_body
    assert page.title in html_body
    assert "A summary of the release." in html_body
    action_url = page.get_full_url()
    assert action_url in html_body
    assert action_url in msg.body

    for href in re.findall(r'href="([^"]*)"', html_body):
        assert href.startswith(("http://", "https://", "mailto:")), href


@pytest.mark.django_db
def test_post_published_email_falls_back_when_display_name_is_blank(
    wagtail_site, make_post_page
):
    author = baker.make("users.User", email="anon@example.com", display_name="")
    page = make_post_page(owner=author)

    send_post_published_email(page.pk)

    html_body = next(
        alt.content
        for alt in mail.outbox[0].alternatives
        if alt.mimetype == "text/html"
    )
    assert "Hi there" in html_body
