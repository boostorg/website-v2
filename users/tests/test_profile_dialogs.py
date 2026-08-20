"""The profile page opens the recognition dialogs from its card CTAs."""

import re

import pytest
import waffle.testutils
from django.test import Client

from badges.enums import AchievementSlug
from badges.models import Achievement
from users.models import User


def render_profile(user):
    """The member's own profile page, as they see it."""
    client = Client()
    client.force_login(user)
    with waffle.testutils.override_flag("v3", active=True):
        return client.get("/users/me/", follow=True).content.decode()


@pytest.fixture
def owner(db, catalogue):
    return User.objects.create_user(email="me@example.com", password="x")


@pytest.fixture
def profile_body(owner):
    """The rendered profile page of a member holding no badges."""
    return render_profile(owner)


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


def test_dialog_shows_the_owners_own_counts(owner, grant_achievement):
    """The counter is the member's tally, not a placeholder."""
    review = Achievement.objects.get(slug=AchievementSlug.LIBRARY_REVIEW)
    grant_achievement(owner, review, count=12)

    body = render_profile(owner)
    dialog = body[body.index('id="achievements-modal"') :]
    row = dialog[dialog.index(review.name) - 400 : dialog.index(review.name)]

    assert ">12<" in row


def test_a_single_digit_count_is_padded(owner, grant_achievement):
    review = Achievement.objects.get(slug=AchievementSlug.LIBRARY_REVIEW)
    grant_achievement(owner, review, count=3)

    body = render_profile(owner)
    dialog = body[body.index('id="achievements-modal"') :]
    row = dialog[dialog.index(review.name) - 400 : dialog.index(review.name)]

    assert ">03<" in row


def test_an_untouched_achievement_counts_zero(owner):
    """Zero on the owner's page, where the answer is known."""
    body = render_profile(owner)
    dialog = body[body.index('id="achievements-modal"') :]

    assert ">00<" in dialog
