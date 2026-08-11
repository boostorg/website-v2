"""Tests for the tier-change signal that keeps configuration edits effective."""

import pytest
from model_bakery import baker

from badges.enums import TierRank
from badges.models import Badge, BadgeTier, UserBadge
from badges.services import deactivate_tier
from badges.tests.fixtures import active_ranks

pytestmark = pytest.mark.django_db


def test_new_tier_awards_qualifying_members(
    plain_user,
    badge,
    achievement,
    grant_achievement,
    django_capture_on_commit_callbacks,
):
    """Adding a tier a member already qualifies for awards it without a sweep."""
    grant_achievement(plain_user, achievement, count=3)
    assert TierRank.PLATINUM.value not in active_ranks(plain_user, badge)

    with django_capture_on_commit_callbacks(execute=True):
        BadgeTier.objects.create(badge=badge, rank=TierRank.PLATINUM, threshold=2)

    assert TierRank.PLATINUM.value in active_ranks(plain_user, badge)


def test_replacing_a_tier_keeps_existing_holders(
    plain_user,
    badge,
    achievement,
    grant_achievement,
    django_capture_on_commit_callbacks,
):
    """Grandfathering: raising a threshold must not revoke what was earned."""
    grant_achievement(plain_user, achievement, count=1)
    bronze = badge.tiers.get(rank=TierRank.BRONZE)
    held = UserBadge.objects.get(user=plain_user, tier=bronze)

    with django_capture_on_commit_callbacks(execute=True):
        deactivate_tier(bronze)
        BadgeTier.objects.create(badge=badge, rank=TierRank.BRONZE, threshold=5)

    held.refresh_from_db()
    assert held.revoked_at is None


def test_lowering_a_threshold_awards_without_a_manual_rebuild(
    plain_user,
    badge,
    achievement,
    grant_achievement,
    django_capture_on_commit_callbacks,
):
    """The retire-and-replace procedure now takes effect on its own."""
    grant_achievement(plain_user, achievement, count=2)
    silver = badge.tiers.get(rank=TierRank.SILVER)  # threshold 3
    assert TierRank.SILVER.value not in active_ranks(plain_user, badge)

    with django_capture_on_commit_callbacks(execute=True):
        deactivate_tier(silver)
        BadgeTier.objects.create(badge=badge, rank=TierRank.SILVER, threshold=2)

    assert TierRank.SILVER.value in active_ranks(plain_user, badge)


def test_tier_change_does_nothing_before_the_transaction_commits(
    plain_user, badge, achievement, grant_achievement
):
    """The work is deferred to commit, which is what keeps the fixtures cheap.

    Under the test transaction no callback runs, so seeding the catalogue does not
    trigger a recalculation per tier.
    """
    grant_achievement(plain_user, achievement, count=3)

    BadgeTier.objects.create(badge=badge, rank=TierRank.PLATINUM, threshold=2)

    assert TierRank.PLATINUM.value not in active_ranks(plain_user, badge)


def test_tier_cascaded_away_with_its_badge_sweeps_harmlessly(
    badge,
    plain_user,
    achievement,
    grant_achievement,
    django_capture_on_commit_callbacks,
):
    """Deleting a badge sweeps its achievement without raising or collateral damage.

    The tier's ``post_delete`` fires mid-cascade and queues a sweep for the whole
    achievement. Under eager celery the task body runs inside that callback, so this
    exercises ``recalculate_achievement_task`` against a graph where the badge that
    triggered it is already gone - in production a crash there would leave the
    achievement silently unrecalculated. The sibling badge's awards must survive it
    untouched.

    Queuing at all depends on the cascade removing tiers before their badge, which is
    what leaves ``achievement_id`` readable; the ``None`` bail-out in the handler is
    for deletes that bypass the ORM, not for this path.

    Only reachable for a badge nobody has earned - see
    ``test_services.test_badge_with_an_awarded_tier_cannot_be_deleted``.
    """
    grant_achievement(plain_user, achievement, count=1)
    other = baker.make(
        Badge, label="documenter", achievement=badge.achievement, description=""
    )
    tier = baker.make(BadgeTier, badge=other, rank=TierRank.BRONZE, threshold=1)
    before = set(UserBadge.objects.values_list("pk", "tier_id", "revoked_at"))

    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        Badge.objects.filter(pk=other.pk).delete()

    assert len(callbacks) == 1
    assert not BadgeTier.objects.filter(pk=tier.pk).exists()
    assert set(UserBadge.objects.values_list("pk", "tier_id", "revoked_at")) == before
