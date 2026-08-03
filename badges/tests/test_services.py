"""Tests for badge recalculation, including signal-driven and cascade paths."""

from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from django.utils import timezone
from model_bakery import baker

from badges.enums import BadgeLabel, TierRank
from badges.models import BadgeTier, RevocationSource, UserAchievement, UserBadge
from badges.services import (
    achievement_pairs,
    deactivate_tier,
    reactivate_tier,
    recalculate_badges,
    replace_tier,
    revocation_cause,
)
from badges.tests.fixtures import ONE_PER_RANK, active_ranks, set_ladder, shift_ladder

pytestmark = pytest.mark.django_db


def test_signal_awards_tier_on_grant(plain_user, badge, achievement, grant_achievement):
    """Creating an achievement awards every tier whose threshold is met."""
    grant_achievement(plain_user, achievement, count=1)
    assert active_ranks(plain_user, badge) == {TierRank.BRONZE.value}

    grant_achievement(plain_user, achievement, count=2)  # total 3
    assert active_ranks(plain_user, badge) == {
        TierRank.BRONZE.value,
        TierRank.SILVER.value,
    }


def test_recalculation_refuses_a_rank_below_one_already_held(
    plain_user, badge, achievement, grant_achievement
):
    """Retuning a ladder upward must not hand a gold holder the new bronze.

    Three grants make the member gold under 1/2/3/4/5. Shifting every rung up by
    five and letting them earn three more puts the count at six, which meets the
    new bronze - and awarding it would record a bronze dated after their gold for
    a member who has done nothing but gain grants.
    """
    set_ladder(badge, ONE_PER_RANK)
    grant_achievement(plain_user, achievement, count=3)
    shift_ladder(badge, 5)

    grant_achievement(plain_user, achievement, count=3)

    assert UserAchievement.objects.filter(user=plain_user, is_valid=True).count() == 6
    assert active_ranks(plain_user, badge) == {
        TierRank.BRONZE.value,
        TierRank.SILVER.value,
        TierRank.GOLD.value,
    }
    # All three are the grandfathered rows against the retired tiers; the retuned
    # ladder has awarded nothing.
    assert not UserBadge.objects.filter(user=plain_user, tier__is_active=True).exists()


def test_recalculation_awards_the_next_rank_up_once_it_is_reached(
    plain_user, badge, achievement, grant_achievement
):
    """The rung above the one held is awarded on its own threshold, and only it."""
    set_ladder(badge, ONE_PER_RANK)
    grant_achievement(plain_user, achievement, count=3)
    shift_ladder(badge, 5)

    grant_achievement(plain_user, achievement, count=6)  # nine, the new platinum

    awarded = UserBadge.objects.get(user=plain_user, tier__is_active=True)
    assert awarded.tier.rank == TierRank.PLATINUM
    assert awarded.tier.threshold == 9


def test_recalculation_re_earns_a_lower_rank_it_had_already_awarded(
    plain_user, badge, achievement, grant_achievement
):
    """The rank floor blocks new awards, never the recovery of an existing badge.

    A cascade revocation still comes back when its count recovers, even for a rank
    now sitting below one the member holds - which only a retuned ladder produces,
    and which rows written before the floor existed still contain.
    """
    set_ladder(badge, ONE_PER_RANK)
    grant_achievement(plain_user, achievement, count=3)
    shift_ladder(badge, 5)
    new_bronze = badge.tiers.get(rank=TierRank.BRONZE, is_active=True)
    bronze_badge = baker.make(UserBadge, user=plain_user, badge=badge, tier=new_bronze)

    # Three grants against a threshold of six: the row it already has is revoked.
    recalculate_badges(plain_user.pk, achievement.pk)
    bronze_badge.refresh_from_db()
    assert bronze_badge.revoked_at is not None
    assert bronze_badge.revocation_source == RevocationSource.CASCADE

    grant_achievement(plain_user, achievement, count=3)

    bronze_badge.refresh_from_db()
    assert bronze_badge.revoked_at is None
    assert bronze_badge.revocation_source == ""


def test_recalculate_is_idempotent(plain_user, badge, achievement, grant_achievement):
    """Repeated recalculation does not create duplicate badge rows."""
    grant_achievement(plain_user, achievement, count=3)
    recalculate_badges(plain_user.pk, achievement.pk)
    recalculate_badges(plain_user.pk, achievement.pk)
    assert UserBadge.objects.filter(user=plain_user, badge=badge).count() == 2


def test_invalidation_cascades_to_badge(
    plain_user, badge, achievement, grant_achievement, super_user
):
    """Invalidating an achievement revokes tiers that fall below threshold."""
    rows = grant_achievement(plain_user, achievement, count=3)
    assert TierRank.SILVER.value in active_ranks(plain_user, badge)

    target = rows[0]
    target.is_valid = False
    target.invalidated_by = super_user
    target.invalidated_at = timezone.now()
    target.invalidation_notes = "Counted in error"
    target.save()

    # count is now 2 -> silver (threshold 3) revoked, bronze (1) retained
    assert active_ranks(plain_user, badge) == {TierRank.BRONZE.value}
    silver = UserBadge.objects.get(
        user=plain_user, badge=badge, tier__rank=TierRank.SILVER
    )
    assert silver.revoked_at is not None
    assert silver.revoked_by == super_user
    assert silver.revocation_notes != ""


def test_re_earn_after_invalidation(
    plain_user, badge, achievement, grant_achievement, super_user
):
    """A revoked tier is re-earned once the count meets the threshold again."""
    rows = grant_achievement(plain_user, achievement, count=3)
    target = rows[0]
    target.is_valid = False
    target.invalidated_by = super_user
    target.invalidated_at = timezone.now()
    target.save()
    assert TierRank.SILVER.value not in active_ranks(plain_user, badge)

    grant_achievement(plain_user, achievement, count=1)  # valid count back to 3
    silver = UserBadge.objects.get(
        user=plain_user, badge=badge, tier__rank=TierRank.SILVER
    )
    assert silver.revoked_at is None
    assert silver.revocation_notes == ""


def test_direct_revocation_does_not_touch_achievements(
    plain_user, badge, achievement, grant_achievement
):
    """A direct badge revocation leaves UserAchievement rows untouched."""
    grant_achievement(plain_user, achievement, count=1)
    bronze = UserBadge.objects.get(
        user=plain_user, badge=badge, tier__rank=TierRank.BRONZE
    )
    bronze.revoked_at = timezone.now()
    bronze.revocation_notes = "Manual revoke"
    bronze.save()

    assert (
        UserAchievement.objects.filter(
            user=plain_user, achievement=achievement, is_valid=True
        ).count()
        == 1
    )


def test_re_earn_after_cascade_revocation_when_count_sufficient(
    plain_user, badge, achievement, grant_achievement, monkeypatch
):
    """A cascade re-earn remains a new award event with a new timestamp."""
    grant_achievement(plain_user, achievement, count=1)
    bronze = UserBadge.objects.get(
        user=plain_user, badge=badge, tier__rank=TierRank.BRONZE
    )
    originally_awarded_at = timezone.datetime(2025, 3, 7, 14, 30, tzinfo=timezone.UTC)
    reearned_at = timezone.datetime(2026, 7, 31, 18, 45, tzinfo=timezone.UTC)
    bronze.awarded_at = originally_awarded_at
    bronze.revoked_at = timezone.now()
    bronze.revocation_source = RevocationSource.CASCADE
    bronze.save()

    monkeypatch.setattr("badges.services.timezone.now", lambda: reearned_at)
    grant_achievement(plain_user, achievement, count=1)  # count now 2 (>=1)
    bronze.refresh_from_db()
    assert bronze.revoked_at is None
    assert bronze.revocation_source == ""
    assert bronze.awarded_at == reearned_at


def test_manual_revocation_survives_recalculation(
    plain_user, badge, achievement, grant_achievement
):
    """A manually revoked badge is not re-earned while it stays revoked."""
    grant_achievement(plain_user, achievement, count=1)
    bronze = UserBadge.objects.get(
        user=plain_user, badge=badge, tier__rank=TierRank.BRONZE
    )
    bronze.revoked_at = timezone.now()
    bronze.revocation_notes = "Removed by an admin"
    bronze.revocation_source = RevocationSource.MANUAL
    bronze.save()

    grant_achievement(plain_user, achievement, count=1)  # count now 2 (>=1)
    recalculate_badges(plain_user.pk, achievement.pk)

    bronze.refresh_from_db()
    assert bronze.revoked_at is not None
    assert bronze.revocation_notes == "Removed by an admin"
    assert bronze.revocation_source == RevocationSource.MANUAL


def test_grandfathering_threshold_change_does_not_revoke(
    plain_user, badge, achievement, grant_achievement
):
    """Changing a threshold does not retroactively revoke existing badges."""
    grant_achievement(plain_user, achievement, count=5)  # bronze+silver+gold
    assert active_ranks(plain_user, badge) == {
        TierRank.BRONZE.value,
        TierRank.SILVER.value,
        TierRank.GOLD.value,
    }

    # Reducing a threshold: no recalculation, nothing revoked.
    silver_tier = badge.tiers.get(rank=TierRank.SILVER)
    silver_tier.threshold = 2
    silver_tier.save()

    # Increasing a threshold above the current count: still not revoked.
    gold_tier = badge.tiers.get(rank=TierRank.GOLD)
    gold_tier.threshold = 10
    gold_tier.save()

    assert active_ranks(plain_user, badge) == {
        TierRank.BRONZE.value,
        TierRank.SILVER.value,
        TierRank.GOLD.value,
    }


def test_hard_delete_triggers_recalculation(
    plain_user, badge, achievement, grant_achievement
):
    """Hard-deleting an achievement recalculates and revokes lost tiers."""
    rows = grant_achievement(plain_user, achievement, count=1)
    assert TierRank.BRONZE.value in active_ranks(plain_user, badge)

    rows[0].delete()
    assert active_ranks(plain_user, badge) == set()


def test_inactive_tier_does_not_grant_new_badges(
    plain_user, badge, achievement, grant_achievement
):
    """A deactivated tier stops granting badges to new earners."""
    silver_tier = badge.tiers.get(rank=TierRank.SILVER)
    silver_tier.is_active = False
    silver_tier.save()

    grant_achievement(plain_user, achievement, count=3)  # would be bronze+silver
    assert active_ranks(plain_user, badge) == {TierRank.BRONZE.value}


def test_deactivating_tier_preserves_existing_user_badges(
    plain_user, badge, achievement, grant_achievement
):
    """Soft-deleting a tier leaves already-earned UserBadge rows intact."""
    grant_achievement(plain_user, achievement, count=3)  # bronze+silver earned
    silver = UserBadge.objects.get(
        user=plain_user, badge=badge, tier__rank=TierRank.SILVER
    )

    silver_tier = badge.tiers.get(rank=TierRank.SILVER)
    silver_tier.is_active = False
    silver_tier.save()

    # A later recalculation must not revoke the preserved badge.
    recalculate_badges(plain_user.pk, achievement.pk)
    silver.refresh_from_db()
    assert silver.revoked_at is None
    assert silver.tier_id == silver_tier.pk


def test_tier_with_earned_badge_cannot_be_hard_deleted(
    plain_user, badge, achievement, grant_achievement
):
    """on_delete=PROTECT stops a tier from being destroyed once earned."""
    grant_achievement(plain_user, achievement, count=1)
    bronze_tier = badge.tiers.get(rank=TierRank.BRONZE)
    with pytest.raises(ProtectedError):
        bronze_tier.delete()


def test_recalculation_noop_when_user_or_achievement_gone(
    achievement, badge, plain_user
):
    """Stale ids are a no-op rather than a crash.

    A missing user counts zero achievements; a missing achievement has nothing to
    reconcile against, so it logs and returns. The ``badge`` fixture is what gives
    the achievement active tiers, without which nothing could be written anyway.
    """
    assert badge.tiers.filter(is_active=True).exists()
    recalculate_badges(99999999, achievement.pk)
    recalculate_badges(99999999, 99999999)
    recalculate_badges(plain_user.pk, 99999999)
    assert not UserBadge.objects.exists()


def test_recalculation_handles_multiple_badges_per_achievement(
    plain_user, badge, achievement, grant_achievement
):
    """One achievement can feed more than one badge."""
    second = baker.make(
        "badges.Badge", label=BadgeLabel.DOCUMENTER, achievement=achievement
    )
    BadgeTier.objects.create(badge=second, rank=TierRank.BRONZE, threshold=1)

    grant_achievement(plain_user, achievement, count=1)
    assert TierRank.BRONZE.value in active_ranks(plain_user, badge)
    assert TierRank.BRONZE.value in active_ranks(plain_user, second)


def test_recalculation_cost_does_not_grow_with_tiers(
    plain_user, badge, achievement, grant_achievement, django_assert_num_queries
):
    """A no-op recalculation costs a fixed number of reads, whatever the tiers.

    The reconciliation loop must not query per tier: a full
    ``manage.py recalculate_badges`` visits every (user, achievement) pair, so a
    per-tier query multiplies across the whole table.
    """
    grant_achievement(plain_user, achievement, count=1)
    assert badge.tiers.filter(is_active=True).count() > 1

    # Five reads - achievement, valid count, badges, prefetched tiers, held
    # badges - plus the savepoint pair from the atomic block.
    with django_assert_num_queries(7):
        recalculate_badges(plain_user.pk, achievement.pk)


def test_deactivate_tier_records_the_actor_once(badge, super_user):
    """A second retirement must not overwrite the original audit trail."""
    bronze = badge.tiers.get(rank=TierRank.BRONZE)
    deactivate_tier(bronze, actor=super_user)
    first_time = bronze.deactivated_at

    deactivate_tier(bronze, actor=None)

    bronze.refresh_from_db()
    assert bronze.deactivated_at == first_time
    assert bronze.deactivated_by == super_user


def test_reactivate_tier_restores_a_retired_tier(badge, super_user):
    """Reactivating clears the retirement so the tier grants again."""
    bronze = badge.tiers.get(rank=TierRank.BRONZE)
    deactivate_tier(bronze, actor=super_user)

    reactivate_tier(bronze)

    bronze.refresh_from_db()
    assert bronze.is_active is True
    assert bronze.deactivated_at is None
    assert bronze.deactivated_by is None


def test_reactivate_tier_refuses_a_taken_rank(badge, super_user):
    """Only one active tier per rank, so a replaced tier cannot come back."""
    bronze = badge.tiers.get(rank=TierRank.BRONZE)
    deactivate_tier(bronze, actor=super_user)
    baker.make("badges.BadgeTier", badge=badge, rank=TierRank.BRONZE, threshold=5)

    with pytest.raises(ValidationError):
        reactivate_tier(bronze)

    bronze.refresh_from_db()
    assert bronze.is_active is False


def test_replace_tier_retires_the_old_row_and_returns_both(badge, super_user):
    """The retired row keeps the old threshold; the new one carries the new."""
    bronze = badge.tiers.get(rank=TierRank.BRONZE)
    bronze.threshold = 5  # the in-memory edit an admin just made

    retired, replacement = replace_tier(bronze, actor=super_user)

    assert retired.pk == bronze.pk
    assert retired.is_active is False
    assert retired.threshold == 1  # re-read, not the in-memory value
    assert retired.deactivated_by == super_user
    assert replacement.pk != bronze.pk
    assert (replacement.rank, replacement.threshold, replacement.is_active) == (
        TierRank.BRONZE,
        5,
        True,
    )


def test_replace_tier_keeps_the_old_tiers_holders(
    plain_user, badge, achievement, grant_achievement
):
    """Grandfathering: raising a threshold must not revoke who already met it."""
    grant_achievement(plain_user, achievement, count=1)
    awarded = UserBadge.objects.get(user=plain_user, tier__rank=TierRank.BRONZE)

    bronze = badge.tiers.get(rank=TierRank.BRONZE)
    bronze.threshold = 5
    replace_tier(bronze)
    recalculate_badges(plain_user.pk, achievement.pk)

    awarded.refresh_from_db()
    assert awarded.revoked_at is None


def test_replace_tier_is_atomic(badge, super_user):
    """A failed replacement must not leave the badge without that rank."""
    bronze = badge.tiers.get(rank=TierRank.BRONZE)
    bronze.threshold = 5

    with patch.object(
        BadgeTier.objects, "create", side_effect=RuntimeError("boom")
    ), pytest.raises(RuntimeError):
        replace_tier(bronze, actor=super_user)

    bronze.refresh_from_db()
    assert bronze.is_active is True
    assert bronze.threshold == 1


def test_achievement_pairs_includes_badge_only_pairs(
    plain_user, badge, achievement, grant_achievement
):
    """A pair whose achievements are gone is still work: its badge needs revoking."""
    grant_achievement(plain_user, achievement, count=1)
    UserAchievement.objects.filter(user=plain_user)._raw_delete(using="default")

    assert set(achievement_pairs()) == {(plain_user.pk, achievement.pk)}


def test_achievement_pairs_scopes_to_one_achievement(
    plain_user, badge, achievement, grant_achievement
):
    """Scoping by achievement excludes other types on both sides of the union."""
    other = baker.make("badges.Achievement", slug="other-achievement")
    grant_achievement(plain_user, achievement, count=1)
    grant_achievement(plain_user, other, count=1)

    assert set(achievement_pairs([achievement.pk])) == {(plain_user.pk, achievement.pk)}


def test_achievement_pairs_scopes_to_one_user(
    plain_user, badge, achievement, grant_achievement
):
    """Scoping by user is how the per-user admin recalculation stays cheap."""
    other_user = baker.make("users.User", email="other-pairs@example.com")
    grant_achievement(plain_user, achievement, count=1)
    grant_achievement(other_user, achievement, count=1)

    assert set(achievement_pairs(user_ids=[plain_user.pk])) == {
        (plain_user.pk, achievement.pk)
    }


def test_cascade_revocation_note_carries_the_arithmetic(
    plain_user, badge, achievement, grant_achievement
):
    """Support's first question is "how far short", so the note has to answer it."""
    grants = grant_achievement(plain_user, achievement, count=3)
    silver = badge.tiers.get(rank=TierRank.SILVER)  # threshold 3

    grants[0].is_valid = False
    grants[0].save()

    revoked = UserBadge.objects.get(user=plain_user, tier=silver)
    assert revoked.count_at_revocation == 2
    assert "2 valid" in revoked.revocation_notes
    assert "Silver" in revoked.revocation_notes
    assert "threshold of 3" in revoked.revocation_notes
    # The old wording blamed an invalidation even when a reconcile had deleted the
    # grants, which sent support looking for a row that was never there.
    assert "invalidated" not in revoked.revocation_notes


def test_revocation_cause_names_the_operation_responsible(
    plain_user, badge, achievement, grant_achievement
):
    """Without a cause, an automated removal revokes with nobody to point at."""
    grants = grant_achievement(plain_user, achievement, count=1)

    with revocation_cause("reconcile of code-commits"):
        grants[0].delete()

    revoked = UserBadge.objects.get(user=plain_user)
    assert "Cause: reconcile of code-commits." in revoked.revocation_notes


def test_re_earning_clears_the_revocation_audit(
    plain_user, badge, achievement, grant_achievement
):
    """A recovered count leaves no stale count_at_revocation behind."""
    grants = grant_achievement(plain_user, achievement, count=1)
    grants[0].is_valid = False
    grants[0].save()
    assert UserBadge.objects.get(user=plain_user).count_at_revocation == 0

    grants[0].is_valid = True
    grants[0].save()

    held = UserBadge.objects.get(user=plain_user)
    assert held.revoked_at is None
    assert held.count_at_revocation is None
    assert held.revocation_notes == ""
