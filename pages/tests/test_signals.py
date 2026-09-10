"""Notifying a PostPage's author and lighting the nav dot once it goes live."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from wagtail.signals import page_published

from pages.notifications import latest_notified_post_id


@pytest.mark.django_db
def test_first_publish_emails_the_author_and_lights_the_dot(
    user, wagtail_site, make_post_page
):
    page = make_post_page(owner=user)
    page.last_published_at = page.first_published_at  # a true first publish

    with patch("pages.signals.send_post_published_email.delay") as delay:
        page_published.send(sender=type(page), instance=page)

    delay.assert_called_once_with(page.pk)
    assert latest_notified_post_id() == page.pk


@pytest.mark.django_db
def test_republish_does_not_email_again(wagtail_site, make_post_page):
    page = make_post_page()
    page.last_published_at = page.first_published_at + timedelta(days=1)

    with patch("pages.signals.send_post_published_email.delay") as delay:
        page_published.send(sender=type(page), instance=page)

    delay.assert_not_called()


@pytest.mark.django_db
def test_not_yet_live_does_not_email(wagtail_site, make_post_page):
    page = make_post_page(live=False)

    with patch("pages.signals.send_post_published_email.delay") as delay:
        page_published.send(sender=type(page), instance=page)

    delay.assert_not_called()


@pytest.mark.django_db
def test_skips_author_with_no_email(user, wagtail_site, make_post_page):
    page = make_post_page(owner=user)
    page.last_published_at = page.first_published_at  # a true first publish
    page.author.email = ""
    page.author.save()

    with patch("pages.signals.send_post_published_email.delay") as delay:
        page_published.send(sender=type(page), instance=page)

    delay.assert_not_called()
