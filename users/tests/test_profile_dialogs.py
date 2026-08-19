"""The profile page opens the recognition dialogs from its card CTAs."""

import re

import pytest
import waffle.testutils
from django.test import Client

from users.models import User


@pytest.fixture
def profile_body(db, catalogue):
    """The rendered profile page of a member holding no badges."""
    user = User.objects.create_user(email="me@example.com", password="x")
    client = Client()
    client.force_login(user)
    with waffle.testutils.override_flag("v3", active=True):
        return client.get("/users/me/", follow=True).content.decode()


def test_profile_page_renders_both_dialogs(profile_body):
    assert 'id="achievements-modal"' in profile_body
    assert 'id="badges-modal"' in profile_body


def test_achievements_cta_opens_its_dialog(profile_body):
    (href,) = re.findall(
        r'<a[^>]*href="([^"]*)"[^>]*>(?:(?!</a>).)*Learn how achievements work',
        profile_body,
        re.S,
    )

    assert href == "#achievements-modal"


def test_badges_cta_opens_its_dialog(profile_body):
    (href,) = re.findall(
        r'<a[^>]*href="([^"]*)"[^>]*aria-label="Explore available badges[^"]*"',
        profile_body,
    )

    assert href == "#badges-modal"
