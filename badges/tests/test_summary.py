"""Tests for the per-user badge summary service."""

import pytest
from django.utils import timezone
from model_bakery import baker

from badges.enums import BadgeLabel, TierRank
from badges.models import (
    Achievement,
    Badge,
    BadgeTier,
    RevocationSource,
    UserAchievement,
    UserBadge,
)
from badges.services import deactivate_tier
from badges.summary import user_badge_summary
from badges.tests.fixtures import ONE_PER_RANK, set_ladder, shift_ladder


def _rows_by_achievement(user):
    """The summary keyed by achievement slug, for rows that name one badge."""
    return {row.achievement.slug: row for row in user_badge_summary(user)}


def _manually_revoke(user_badge, actor, note):
    """Revoke the way the admin's revoke action does."""
    user_badge.revoked_at = timezone.now()
    user_badge.revoked_by = actor
    user_badge.revocation_notes = note
    user_badge.revocation_source = RevocationSource.MANUAL
    user_badge.save()


def test_summary_covers_every_achievement_type(catalogue, plain_user):
    """Every type appears, in achievement-name order, even with no grants."""
    rows = user_badge_summary(plain_user)

    assert len(rows) == Achievement.objects.count() == 8
    assert [row.achievement.name for row in rows] == sorted(
        Achievement.objects.values_list("name", flat=True)
    )
    assert all(row.badge is not None for row in rows)
    assert all(row.valid_grants == 0 for row in rows)


def test_summary_reports_the_gap_to_the_next_tier(
    badge, achievement, plain_user, grant_achievement
):
    """Two of the three needed for silver leaves a gap of one."""
    grant_achievement(plain_user, achievement, count=2)

    row = _rows_by_achievement(plain_user)["code-contribution"]

    assert row.valid_grants == 2
    assert row.next_tier.rank == TierRank.SILVER
    assert row.next_tier.threshold == 3
    assert row.gap == 1
    assert row.held.tier.rank == TierRank.BRONZE


def test_summary_names_the_next_rank_up_after_every_threshold_shifts(
    badge, achievement, plain_user, grant_achievement
):
    """A gold holder's next rung is platinum, whatever the thresholds became.

    The reported bug. Three grants make the member gold under 1/2/3/4/5; adding
    five to every rung leaves those three grants meeting nothing at all, so the
    lowest *unmet threshold* is the new bronze at six. Bronze is not a rung
    anybody climbs to from gold - platinum is, and it needs nine.
    """
    set_ladder(badge, ONE_PER_RANK)
    grant_achievement(plain_user, achievement, count=3)
    assert _rows_by_achievement(plain_user)["code-contribution"].held.tier.rank == (
        TierRank.GOLD
    )

    shift_ladder(badge, 5)

    row = _rows_by_achievement(plain_user)["code-contribution"]
    assert row.held.tier.rank == TierRank.GOLD
    assert row.next_tier.rank == TierRank.PLATINUM
    assert row.next_tier.threshold == 9
    assert row.gap == 6


def test_summary_reads_the_current_rank_by_rank_not_by_threshold(
    badge, achievement, plain_user, grant_achievement
):
    """A bronze earned at a higher threshold than an older gold is still bronze.

    Recalculation no longer creates rows like this, but a database written before
    it stopped - or a restored dump - still holds them, and ranking the member's
    badges by threshold would report this one as a promotion to bronze.
    """
    set_ladder(badge, ONE_PER_RANK)
    grant_achievement(plain_user, achievement, count=3)
    shift_ladder(badge, 5)
    new_bronze = badge.tiers.get(rank=TierRank.BRONZE, is_active=True)
    baker.make(UserBadge, user=plain_user, badge=badge, tier=new_bronze)

    row = _rows_by_achievement(plain_user)["code-contribution"]

    assert new_bronze.threshold == 6
    assert row.held.tier.rank == TierRank.GOLD
    assert row.held.tier.threshold == 3


def test_summary_skips_a_manually_revoked_rank_when_naming_the_next_one(
    badge, achievement, plain_user, grant_achievement, super_user
):
    """A rank recalculation refuses to give back is not the rung anyone awaits.

    The member holds bronze and had silver taken away by hand. Silver's threshold
    is met and will stay met, and no number of new grants brings it back, so the
    next rung they can actually reach is gold.
    """
    grant_achievement(plain_user, achievement, count=3)
    _manually_revoke(
        UserBadge.objects.get(user=plain_user, tier__rank=TierRank.SILVER),
        super_user,
        "Duplicate reviews.",
    )

    row = _rows_by_achievement(plain_user)["code-contribution"]

    assert row.held.tier.rank == TierRank.BRONZE
    assert row.next_tier.rank == TierRank.GOLD
    assert row.gap == 2


def test_summary_reports_a_manual_revocation_with_its_note(
    badge, achievement, plain_user, grant_achievement, super_user
):
    """The reason names who revoked it, when, and why."""
    grant_achievement(plain_user, achievement, count=1)
    _manually_revoke(
        UserBadge.objects.get(user=plain_user), super_user, "Spam account."
    )

    row = _rows_by_achievement(plain_user)["code-contribution"]

    assert row.held is None
    assert len(row.revoked) == 1
    assert str(super_user) in row.reason
    assert "Spam account." in row.reason


def test_summary_reports_a_cascade_revocation_with_the_count(
    badge, achievement, plain_user, grant_achievement
):
    """A cascade revocation is explained as a count against a threshold."""
    grant_achievement(plain_user, achievement, count=1)
    grant = UserAchievement.objects.get(user=plain_user)
    grant.is_valid = False
    grant.save()

    row = _rows_by_achievement(plain_user)["code-contribution"]

    assert row.held is None
    assert row.valid_grants == 0
    assert row.invalid_grants == 1
    assert row.reason == "Revoked automatically - 0 valid grants, needs 1."


def test_summary_prefers_a_manual_revocation_over_a_cascade(
    badge, achievement, plain_user, grant_achievement, super_user
):
    """A manual revocation survives recalculation, so it is the real blocker."""
    grant_achievement(plain_user, achievement, count=3)
    bronze = UserBadge.objects.get(user=plain_user, tier__rank=TierRank.BRONZE)
    _manually_revoke(bronze, super_user, "Under review.")
    grant = UserAchievement.objects.filter(user=plain_user).first()
    grant.is_valid = False
    grant.save()

    row = _rows_by_achievement(plain_user)["code-contribution"]

    assert {entry.revocation_source for entry in row.revoked} == {
        RevocationSource.MANUAL,
        RevocationSource.CASCADE,
    }
    assert "Under review." in row.reason


def test_summary_reports_hidden_badges(
    badge, achievement, plain_user, grant_achievement
):
    """A held badge the member has switched off is not a missing badge."""
    grant_achievement(plain_user, achievement, count=1)
    plain_user.hide_badges = True
    plain_user.save()

    row = _rows_by_achievement(plain_user)["code-contribution"]

    assert row.held is not None
    assert row.reason == ("Held, but hidden - the member has turned badge display off.")


def test_summary_reports_a_badge_with_no_active_tiers(badge, plain_user):
    """The misconfiguration that makes a badge unawardable."""
    for tier in badge.tiers.all():
        deactivate_tier(tier)

    row = _rows_by_achievement(plain_user)["code-contribution"]

    assert row.next_tier is None
    assert row.gap is None
    assert row.reason == "The badge has no active tiers, so it awards nothing."


def test_summary_reports_an_achievement_with_no_badge(achievement, plain_user):
    """Grants that can never become anything still get a row."""
    row = _rows_by_achievement(plain_user)["code-contribution"]

    assert row.badge is None
    assert row.reason == "No badge is configured for this achievement."


def test_summary_reports_a_badge_held_below_its_threshold(
    badge, achievement, plain_user, grant_achievement
):
    """A badge whose grants vanished without a recalculation is flagged."""
    grant_achievement(plain_user, achievement, count=1)
    # A bulk delete: no post_delete receivers, so nothing revokes the badge.
    UserAchievement.objects.filter(user=plain_user)._raw_delete(using="default")

    row = _rows_by_achievement(plain_user)["code-contribution"]

    assert row.held is not None
    assert "only 0 valid grants against a threshold of 1" in row.reason
    assert "Recalculate" in row.reason


def test_summary_reports_grants_that_were_never_awarded(badge, achievement, plain_user):
    """Grants meeting every threshold with no badge row is the inverse stale case."""
    # bulk_create sends no post_save, so no recalculation runs.
    UserAchievement.objects.bulk_create(
        [UserAchievement(user=plain_user, achievement=achievement) for _ in range(5)]
    )

    row = _rows_by_achievement(plain_user)["code-contribution"]

    assert row.held is None
    # Holding nothing puts the member at the bottom of the ladder, so the next
    # rung is bronze even though its threshold - and every other - is already met.
    assert row.next_tier.rank == TierRank.BRONZE
    assert row.gap == 0
    assert row.reason == (
        "Not earned, but 5 valid grants already reaches Gold. "
        "Recalculate to award it."
    )


def test_summary_gives_an_achievement_a_row_per_badge(
    badge, achievement, plain_user, grant_achievement
):
    """Two badges over one achievement have separate ladders and answers."""
    second = baker.make(Badge, label=BadgeLabel.REGULAR, achievement=achievement)
    baker.make(BadgeTier, badge=second, rank=TierRank.BRONZE, threshold=10)
    grant_achievement(plain_user, achievement, count=1)

    rows = [row for row in user_badge_summary(plain_user) if row.badge is not None]

    assert len(rows) == 2
    by_label = {row.badge.label: row for row in rows}
    assert by_label[BadgeLabel.MAINTAINER].held is not None
    assert by_label[BadgeLabel.REGULAR].held is None
    assert by_label[BadgeLabel.REGULAR].gap == 9


@pytest.mark.parametrize("count", [1, 8])
def test_summary_query_count_is_flat(db, plain_user, django_assert_num_queries, count):
    """The cost does not grow with the number of achievement types."""
    for label in list(BadgeLabel)[:count]:
        achievement = baker.make(Achievement, name=label.label, slug=label.value)
        new_badge = baker.make(Badge, label=label, achievement=achievement)
        baker.make(BadgeTier, badge=new_badge, rank=TierRank.BRONZE, threshold=1)

    with django_assert_num_queries(5):
        rows = user_badge_summary(plain_user)

    assert len(rows) == count


def test_summary_query_count_survives_revocations(
    badge,
    achievement,
    plain_user,
    grant_achievement,
    super_user,
    django_assert_num_queries,
):
    """Naming the revoking admin must not cost a query per revoked badge."""
    grant_achievement(plain_user, achievement, count=3)
    for user_badge in UserBadge.objects.filter(user=plain_user):
        _manually_revoke(user_badge, super_user, "Under review.")

    with django_assert_num_queries(5):
        rows = user_badge_summary(plain_user)

    assert "Revoked by" in rows[0].reason
