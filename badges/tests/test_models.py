"""Tests for the badge models' constraints and derived properties."""

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from badges.enums import TierRank
from badges.models import BadgeTier, UserAchievement, UserBadge


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


def test_user_badge_unique_together(badge, plain_user):
    """A user cannot hold the same (badge, tier) twice."""
    tier = badge.tiers.get(rank=TierRank.BRONZE)
    UserBadge.objects.create(badge=badge, user=plain_user, tier=tier)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            UserBadge.objects.create(badge=badge, user=plain_user, tier=tier)


def test_user_badge_is_active_property(badge, plain_user):
    tier = badge.tiers.get(rank=TierRank.BRONZE)
    ub = UserBadge.objects.create(badge=badge, user=plain_user, tier=tier)
    assert ub.is_active is True
