"""Tests for the display-badge picker rows."""

from django.utils import timezone

from badges.display import badge_options, default_option, resolve_selection
from badges.enums import BadgeLabel, TierRank
from badges.models import Achievement, RevocationSource, UserBadge
from badges.services import deactivate_tier


def _rows_for(user, label):
    """The picker rows belonging to one badge, in picker order."""
    display = BadgeLabel(label).label
    return [row for row in badge_options(user) if row["name"] == display]


def test_earned_tier_is_selectable_and_names_its_user_badge(
    badge, plain_user, achievement, grant_achievement
):
    """An earned rung carries the UserBadge pk, which is what gets stored."""
    grant_achievement(plain_user, achievement, count=1)

    bronze = _rows_for(plain_user, BadgeLabel.MAINTAINER)[0]
    user_badge = UserBadge.objects.get(user=plain_user, tier__rank=TierRank.BRONZE)

    assert bronze["selectable"] is True
    assert bronze["value"] == user_badge.pk


def test_started_badge_shows_only_the_rank_held(
    catalogue, plain_user, grant_achievement
):
    """One row, the rung held - its copy carries the next. Four grants reach gold."""
    grant_achievement(plain_user, Achievement.objects.get(slug="library-authoring"), 4)

    rows = _rows_for(plain_user, BadgeLabel.LIBRARY_AUTHOR)

    assert [(row["rank"], row["selectable"]) for row in rows] == [("Gold", True)]


def test_unstarted_badge_shows_only_its_first_tier(
    catalogue, plain_user, grant_achievement
):
    """A badge not started offers its bottom rung and nothing above it."""
    grant_achievement(plain_user, Achievement.objects.get(slug="library-authoring"), 4)

    rows = _rows_for(plain_user, BadgeLabel.DOCUMENTER)

    assert [(row["rank"], row["selectable"]) for row in rows] == [("Bronze", False)]


def test_locked_badges_read_in_catalogue_order(catalogue, plain_user):
    """Locked categories follow BadgeLabel's declaration order."""
    names = list(dict.fromkeys(row["name"] for row in badge_options(plain_user)))

    assert names == [label.label for label in BadgeLabel]


def test_unlocked_badges_lead_highest_rank_first(
    catalogue, plain_user, grant_achievement
):
    """The picker opens on what the member has earned, best badge first."""
    grant_achievement(plain_user, Achievement.objects.get(slug="library-authoring"), 4)
    grant_achievement(plain_user, Achievement.objects.get(slug="documentation"), 1)

    names = [row["name"] for row in badge_options(plain_user) if row["selectable"]]

    assert names[0] == BadgeLabel.LIBRARY_AUTHOR.label
    assert names[-1] == BadgeLabel.DOCUMENTER.label


def test_manually_revoked_tier_is_not_selectable(
    badge, plain_user, achievement, grant_achievement
):
    """A manual revocation survives recalculation, so its rung can never be picked."""
    grant_achievement(plain_user, achievement, count=1)
    user_badge = UserBadge.objects.get(user=plain_user, tier__rank=TierRank.BRONZE)
    user_badge.revoked_at = timezone.now()
    user_badge.revocation_source = RevocationSource.MANUAL
    user_badge.save()

    bronze = _rows_for(plain_user, BadgeLabel.MAINTAINER)[0]

    assert bronze["selectable"] is False


def test_retired_tier_still_held_keeps_its_row(
    badge, plain_user, achievement, grant_achievement
):
    """Retiring a rung keeps its badges, so the picker must keep offering it."""
    grant_achievement(plain_user, achievement, count=1)
    user_badge = UserBadge.objects.get(user=plain_user, tier__rank=TierRank.BRONZE)
    deactivate_tier(user_badge.tier)

    rows = _rows_for(plain_user, BadgeLabel.MAINTAINER)

    assert [row["value"] for row in rows if row["selectable"]] == [user_badge.pk]


def test_default_option_picks_the_highest_rank(
    catalogue, plain_user, grant_achievement
):
    """The badge to open on is the best one held, whatever its category."""
    # Documenter bronze needs 1; library authoring's 4 grants reach gold.
    grant_achievement(plain_user, Achievement.objects.get(slug="documentation"), 1)
    grant_achievement(plain_user, Achievement.objects.get(slug="library-authoring"), 4)

    rows = badge_options(plain_user)
    gold = UserBadge.objects.get(user=plain_user, tier__rank=TierRank.GOLD)

    assert default_option(rows) == gold.pk


def test_default_option_breaks_rank_ties_by_catalogue_order(
    catalogue, plain_user, grant_achievement
):
    """Two badges at the same rank: the one declared first in BadgeLabel wins."""
    # Both bronze at one grant, and Documenter sorts after Library Author.
    grant_achievement(plain_user, Achievement.objects.get(slug="documentation"), 1)
    grant_achievement(plain_user, Achievement.objects.get(slug="library-authoring"), 1)

    rows = badge_options(plain_user)
    chosen = UserBadge.objects.get(pk=default_option(rows))

    assert chosen.badge.label == BadgeLabel.LIBRARY_AUTHOR


def test_default_option_is_none_without_a_badge(catalogue, plain_user):
    """Nothing held, nothing to open on."""
    assert default_option(badge_options(plain_user)) is None


def test_resolve_selection_replaces_a_rung_the_member_climbed_past(
    catalogue, plain_user, grant_achievement
):
    """Climbing retires the lower row without revoking it, so the pk must move up.

    Seeding a value the picker no longer lists leaves the trigger blank.
    """
    authoring = Achievement.objects.get(slug="library-authoring")
    grant_achievement(plain_user, authoring, 1)
    bronze = UserBadge.objects.get(user=plain_user, tier__rank=TierRank.BRONZE)
    grant_achievement(plain_user, authoring, 3)
    gold = UserBadge.objects.get(user=plain_user, tier__rank=TierRank.GOLD)

    assert bronze.is_active
    assert resolve_selection(badge_options(plain_user), bronze.pk) == gold.pk


def test_a_cascade_re_earn_returns_the_row_the_member_selected(
    badge, plain_user, achievement, grant_achievement
):
    """A cascade revocation and its re-earn reuse one row, so a stored pk survives.

    ``services._award_tier`` clears the revocation fields rather than creating a
    second ``UserBadge``. Were that to change, a stored selection would be left
    pointing at a row that never comes back.
    """
    grants = grant_achievement(plain_user, achievement, count=3)
    silver = UserBadge.objects.get(user=plain_user, tier__rank=TierRank.SILVER)

    # Count falls to 2, below silver's threshold of 3.
    grants[0].is_valid = False
    grants[0].save()

    silver.refresh_from_db()
    assert silver.revocation_source == RevocationSource.CASCADE
    assert resolve_selection(badge_options(plain_user), silver.pk) != silver.pk

    grant_achievement(plain_user, achievement, count=1)

    silver.refresh_from_db()
    assert silver.is_active
    assert resolve_selection(badge_options(plain_user), silver.pk) == silver.pk


def test_resolve_selection_keeps_a_choice_the_picker_still_offers(
    catalogue, plain_user, grant_achievement
):
    """A deliberate choice outranks the default, which is only a fallback."""
    grant_achievement(plain_user, Achievement.objects.get(slug="library-authoring"), 4)
    grant_achievement(plain_user, Achievement.objects.get(slug="documentation"), 1)
    documenter = UserBadge.objects.get(user=plain_user, badge__label="documenter")

    options = badge_options(plain_user)

    assert default_option(options) != documenter.pk
    assert resolve_selection(options, documenter.pk) == documenter.pk
