"""Notifying a PostPage's author once Wagtail's moderation workflow approves it."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from wagtail.signals import workflow_approved

from pages.signals import notify_post_author_on_approval


@pytest.mark.django_db
def test_workflow_approved_emails_the_post_author(user, wagtail_site, make_post_page):
    page = make_post_page(owner=user)

    with patch("pages.signals.send_post_approved_email.delay") as delay:
        workflow_approved.send(
            sender=object(),
            instance=SimpleNamespace(content_object=page),
            user=user,
        )

    delay.assert_called_once_with(page.pk)


@pytest.mark.django_db
def test_workflow_approved_ignores_non_post_page_content(user):
    with patch("pages.signals.send_post_approved_email.delay") as delay:
        workflow_approved.send(
            sender=object(),
            instance=SimpleNamespace(content_object=SimpleNamespace()),
            user=user,
        )

    delay.assert_not_called()


@pytest.mark.django_db
def test_workflow_approved_skips_author_with_no_email(wagtail_site, make_post_page):
    author = SimpleNamespace(email="", display_name="No Email")
    page = make_post_page()
    page.author = author

    with patch("pages.signals.send_post_approved_email.delay") as delay:
        notify_post_author_on_approval(
            sender=object(),
            instance=SimpleNamespace(content_object=page),
            user=None,
        )

    delay.assert_not_called()
