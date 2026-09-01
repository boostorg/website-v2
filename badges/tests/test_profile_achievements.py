"""What the profile's Achievements card is built from.

Separate from ``test_profile``, which covers the badges half of the same card
column: badges hang off a tier ladder, achievements are a flat tally, and the
two answer different questions.
"""

import pytest
import waffle.testutils
from django.db import connection
from django.test.utils import CaptureQueriesContext

from badges import display
from badges.enums import BadgeLabel
from badges.models import Achievement, Badge, UserAchievement
from badges.summary import user_badge_summary


@pytest.fixture(autouse=True)
def _catalogue(catalogue):
    """Seed the real achievement catalogue for every test in this module."""


def _grant(user, slug, count=1):
    """Grant `count` manual achievements of `slug` (recalcs via the signal)."""
    achievement = Achievement.objects.get(slug=slug)
    for _ in range(count):
        UserAchievement.objects.create(
            user=user, achievement=achievement, source_type="manual"
        )
    return achievement


def test_no_achievements_yields_no_cards(plain_user):
    """A member who has earned nothing gets no rows, not a zeroed catalogue."""
    assert display.achievement_cards(plain_user) == []


def test_an_earned_achievement_becomes_a_card(plain_user):
    """The card carries the achievement's own name, description and tally."""
    achievement = _grant(plain_user, "library-review", count=3)

    (card,) = display.achievement_cards(plain_user)

    assert card["title"] == achievement.name
    assert card["description"] == achievement.description
    assert card["points"] == 3


def test_untouched_achievements_are_left_out(plain_user):
    """Only what the member did. The catalogue is not a checklist to display."""
    _grant(plain_user, "library-review")

    titles = [card["title"] for card in display.achievement_cards(plain_user)]

    assert len(titles) == 1
    assert Achievement.objects.count() > 1


def test_invalidated_grants_do_not_count(plain_user):
    """Invalidation is soft, so the rows survive; the tally must not."""
    _grant(plain_user, "library-review", count=3)
    UserAchievement.objects.filter(user=plain_user).update(is_valid=False)

    assert display.achievement_cards(plain_user) == []


def test_cards_lead_with_the_biggest_tally(plain_user):
    """The tally is the point of the card, and the registry orders by name."""
    _grant(plain_user, "library-review", count=2)
    _grant(plain_user, "code-commits", count=9)

    cards = display.achievement_cards(plain_user)

    assert [card["points"] for card in cards] == [9, 2]


def test_an_achievement_feeding_two_badges_is_one_card(plain_user):
    """``user_badge_summary`` rows are per achievement/badge pair, cards are not.

    One achievement can feed several badges, each with its own ladder. The
    member still did one thing that many times, so it is one row on the card.
    """
    achievement = _grant(plain_user, "library-review", count=3)
    # Repointed rather than created: the catalogue already holds every label,
    # and ``Badge.label`` is unique.
    second = Badge.objects.get(label=BadgeLabel.PUBLISHER)
    second.achievement = achievement
    second.save(update_fields=["achievement"])

    assert achievement.badges.count() == 2

    (card,) = display.achievement_cards(plain_user)

    assert card["points"] == 3


def test_supplied_rows_are_read_instead_of_queried(
    plain_user, django_assert_num_queries
):
    """Both readers take the same rows, so the owner's page reads them once.

    The cards and the dialog's counts are the same underlying summary. Each
    reading it for itself cost the owner's own profile a second copy of every
    query behind it.
    """
    _grant(plain_user, "library-review", count=3)
    rows = user_badge_summary(plain_user)

    with django_assert_num_queries(0):
        cards = display.achievement_cards(plain_user, rows=rows)
    # One, not none: the dialog lists the whole catalogue, which is a read of
    # its own and nothing to do with this member's grants.
    with django_assert_num_queries(1):
        counts = display.achievement_dialog_rows(plain_user, rows=rows)

    assert cards == display.achievement_cards(plain_user)
    assert counts == display.achievement_dialog_rows(plain_user)


@waffle.testutils.override_flag("v3", active=True)
def test_the_owners_page_reads_the_summary_once(plain_user, tp):
    """A regression guard on the page, not just on the functions.

    The owner's page is the only one wanting both the cards and the dialog
    counts, so it is the only one that could pay twice.
    """
    _grant(plain_user, "library-review", count=3)
    tp.client.force_login(plain_user)

    with CaptureQueriesContext(connection) as queries:
        response = tp.get(tp.reverse("profile-account"))

    tp.response_200(response)
    grant_reads = [
        query
        for query in queries.captured_queries
        if "badges_userachievement" in query["sql"]
    ]
    assert len(grant_reads) == 1


@waffle.testutils.override_flag("v3", active=True)
def test_public_profile_renders_the_earned_achievements(plain_user, tp):
    """The reported bug: a member's real achievements never reached the page.

    A visitor, not the owner, because the card used to render for the owner
    alone - and then only as an example.
    """
    achievement = _grant(plain_user, "library-review", count=3)

    response = tp.get(plain_user.get_absolute_url())

    tp.response_200(response)
    body = response.content.decode()
    assert "user-profile__achievements" in body
    assert achievement.name in body
    assert "Showcase your contributions" not in body


@waffle.testutils.override_flag("v3", active=True)
def test_own_profile_keeps_the_empty_achievements_card(plain_user, tp):
    """The owner's empty card carries the only way into the achievements dialog.

    The same rule as the badges card beside it, so the two behave alike.
    """
    tp.client.force_login(plain_user)

    response = tp.get(tp.reverse("profile-account"))

    tp.response_200(response)
    body = response.content.decode()
    assert "user-profile__achievements" in body
    assert "Learn how achievements work" in body


@waffle.testutils.override_flag("v3", active=True)
def test_a_visitor_sees_no_empty_achievements_card(plain_user, tp):
    """The empty state is the owner's prompt to earn some, not a visitor's."""
    response = tp.get(plain_user.get_absolute_url())

    tp.response_200(response)
    assert "user-profile__achievements" not in response.content.decode()
