"""Tests for the badge models' constraints and derived properties."""

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from badges.enums import TierRank
from badges.models import (
    BadgeTier,
    RevocationSource,
    UserAchievement,
    UserBadge,
)


def test_generic_source_reference(plain_user, achievement):
    """An automatic achievement can point at any model via GenericForeignKey."""
    other = ContentType.objects.get_for_model(type(plain_user))
    ua = UserAchievement.objects.create(
        user=plain_user, achievement=achievement, source=plain_user
    )
    ua.refresh_from_db()
    assert ua.source == plain_user
    assert ua.source_content_type == other
    assert ua.source_object_id == plain_user.pk


def test_badge_tier_unique_together(badge):
    """A badge cannot have two tiers with the same rank."""
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            BadgeTier.objects.create(badge=badge, rank=TierRank.BRONZE, threshold=99)


def test_duplicate_active_tier_raises_friendly_error(badge):
    """clean() blocks a second active tier for the same badge and rank."""
    duplicate = BadgeTier(badge=badge, rank=TierRank.BRONZE, threshold=99)
    with pytest.raises(ValidationError) as exc:
        duplicate.full_clean()
    assert "rank" in exc.value.message_dict


def test_inactive_tier_frees_up_the_rank(badge):
    """Deactivating a tier lets a new active tier of the same rank be added."""
    bronze = badge.tiers.get(rank=TierRank.BRONZE)
    bronze.is_active = False
    bronze.deactivated_at = timezone.now()
    bronze.save()

    replacement = BadgeTier(badge=badge, rank=TierRank.BRONZE, threshold=2)
    replacement.full_clean()  # should not raise
    replacement.save()
    assert badge.tiers.filter(rank=TierRank.BRONZE, is_active=True).count() == 1


def test_user_badge_unique_per_tier(badge, plain_user):
    """A member cannot hold the same (badge, tier) twice."""
    tier = badge.tiers.get(rank=TierRank.BRONZE)
    UserBadge.objects.create(badge=badge, user=plain_user, tier=tier)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            UserBadge.objects.create(badge=badge, user=plain_user, tier=tier)


def test_user_badge_is_active_property(badge, plain_user):
    """An un-revoked badge is held."""
    tier = badge.tiers.get(rank=TierRank.BRONZE)
    ub = UserBadge.objects.create(badge=badge, user=plain_user, tier=tier)
    assert ub.is_active is True


def test_user_badge_is_inactive_once_revoked(badge, plain_user):
    """Revoking flips ``is_active`` and drops the row out of ``active()``."""
    tier = badge.tiers.get(rank=TierRank.BRONZE)
    held = UserBadge.objects.create(
        badge=badge, user=plain_user, tier=badge.tiers.get(rank=TierRank.SILVER)
    )
    revoked = UserBadge.objects.create(badge=badge, user=plain_user, tier=tier)

    revoked.revoked_at = timezone.now()
    revoked.revocation_source = RevocationSource.MANUAL
    revoked.save()

    revoked.refresh_from_db()
    assert revoked.is_active is False
    assert set(UserBadge.objects.active().values_list("pk", flat=True)) == {held.pk}


def test_threshold_must_exceed_the_rank_below(badge):
    """Silver cannot be dragged down onto bronze."""
    silver = badge.tiers.get(rank=TierRank.SILVER)  # bronze 1, silver 3, gold 5
    silver.threshold = 1

    with pytest.raises(ValidationError) as exc:
        silver.full_clean()
    assert "threshold" in exc.value.message_dict


def test_threshold_must_stay_below_the_rank_above(badge):
    """Silver cannot be pushed up onto gold."""
    silver = badge.tiers.get(rank=TierRank.SILVER)
    silver.threshold = 5

    with pytest.raises(ValidationError) as exc:
        silver.full_clean()
    assert "threshold" in exc.value.message_dict


def test_threshold_between_its_neighbours_is_accepted(badge):
    """The whole point: a value strictly inside the gap is fine."""
    silver = badge.tiers.get(rank=TierRank.SILVER)
    silver.threshold = 4

    silver.full_clean()  # should not raise


def test_retired_tiers_do_not_constrain_a_threshold(badge):
    """A retuned badge keeps retired rows, which must not block the live ladder."""
    gold = badge.tiers.get(rank=TierRank.GOLD)
    gold.is_active = False
    gold.deactivated_at = timezone.now()
    gold.save()

    silver = badge.tiers.get(rank=TierRank.SILVER)
    silver.threshold = 99  # above the retired gold, with no active rank above it

    silver.full_clean()  # should not raise
