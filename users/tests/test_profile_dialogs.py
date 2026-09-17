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


@pytest.fixture
def decorated_profile_body(owner, grant_achievement):
    """The page of a member who has earned something.

    A filled achievements card, which is the state that drops the CTA.
    """
    review = Achievement.objects.get(slug=AchievementSlug.LIBRARY_REVIEW)
    grant_achievement(owner, review)
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


def test_an_untouched_achievement_shows_a_real_zero(owner):
    """A live member's own page shows their real tally, zero included.

    Only a caller holding no member - a non-profile surface - falls back to
    the Bronze-threshold placeholder.
    """
    body = render_profile(owner)
    dialog = body[body.index('id="achievements-modal"') :]

    assert ">00<" in dialog


def test_an_untouched_achievement_names_what_bronze_takes(owner):
    """The owner's own view says what's needed for the next tier not reached."""
    review = Achievement.objects.get(slug=AchievementSlug.LIBRARY_REVIEW)

    body = render_profile(owner)
    dialog = body[body.index('id="achievements-modal"') :]

    assert f"bronze badge for {review.name}" in dialog


def test_a_filled_achievements_card_drops_the_cta(decorated_profile_body):
    """The button is the empty state's, the same way the badges card works."""
    assert "Showcase your contributions" not in decorated_profile_body
    assert "Learn how achievements work" not in decorated_profile_body
