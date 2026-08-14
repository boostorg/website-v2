"""Shared fixtures and helpers for the badges tests.

Registered as a pytest plugin in the root ``conftest.py``, so the fixtures are
available everywhere; the plain helpers have to be imported.
"""

import pytest
from django.contrib.contenttypes.models import ContentType
from model_bakery import baker

from badges.enums import BadgeLabel, TierRank
from badges.models import (
    Achievement,
    Badge,
    BadgeTier,
    SourceType,
    UserAchievement,
    UserBadge,
)
from badges.seed_data import seed_catalogue
from badges.services import replace_tier

# One grant per rung, so a shift moves all five rungs together.
ONE_PER_RANK = {
    TierRank.BRONZE: 1,
    TierRank.SILVER: 2,
    TierRank.GOLD: 3,
    TierRank.PLATINUM: 4,
    TierRank.DIAMOND: 5,
}


def grant_from_source(user, achievement, source):
    """Record one automatic grant pointing at ``source``.

    ``get_or_create`` rather than ``create``, so a test can assert that a repeat
    is a no-op.
    """
    return UserAchievement.objects.get_or_create(
        user=user,
        achievement=achievement,
        source_content_type=ContentType.objects.get_for_model(source),
        source_object_id=source.pk,
        defaults={"source_type": SourceType.AUTOMATIC},
    )


def set_ladder(badge, thresholds):
    """Replace a badge's tiers with one active tier per rank in ``thresholds``.

    The ``badge`` fixture stops at gold, which cannot express "the rank above the
    one I hold" for a gold holder. Only safe before anything has been awarded.
    """
    badge.tiers.all().delete()
    return [
        baker.make(BadgeTier, badge=badge, rank=rank, threshold=threshold)
        for rank, threshold in thresholds.items()
    ]


def shift_ladder(badge, by):
    """Add ``by`` to every active threshold, through the supported path.

    ``replace_tier`` rather than an in-place update, so it leaves the shape a real
    retuning leaves: the old tiers retired with their badges intact, and new
    active tiers carrying the new numbers.
    """
    for tier in list(badge.tiers.filter(is_active=True)):
        tier.threshold += by
        replace_tier(tier)


def active_ranks(user, badge):
    """The ranks of ``badge`` the member currently holds, read from the database."""
    return set(
        UserBadge.objects.filter(
            user=user, badge=badge, revoked_at__isnull=True
        ).values_list("tier__rank", flat=True)
    )


@pytest.fixture
def catalogue(db):
    """Seed the real achievement catalogue (data migrations are off in tests)."""
    seed_catalogue(Achievement, Badge, BadgeTier)


@pytest.fixture
def achievement(db):
    """A single achievement type."""
    return baker.make(Achievement, name="Code Contribution", slug="code-contribution")


@pytest.fixture
def badge(db, achievement):
    """A maintainer badge with bronze/silver/gold tiers (1/3/5).

    Do not combine with ``catalogue``: both claim the maintainer label. Requested
    after it, this raises on the unique label; requested before it, the seed keeps
    this badge and tops it up, leaving a ladder mixed from both fixtures.
    """
    badge = baker.make(Badge, label=BadgeLabel.MAINTAINER, achievement=achievement)
    baker.make(BadgeTier, badge=badge, rank=TierRank.BRONZE, threshold=1)
    baker.make(BadgeTier, badge=badge, rank=TierRank.SILVER, threshold=3)
    baker.make(BadgeTier, badge=badge, rank=TierRank.GOLD, threshold=5)
    return badge


@pytest.fixture
def plain_user(db):
    """A lightweight user (no profile image) for badge tests."""
    return baker.make("users.User", email="badge-user@example.com")


@pytest.fixture
def grant_achievement(db):
    """Return a helper that creates valid UserAchievement rows.

    Manual on purpose. The field defaults to automatic, and an automatic row with
    no source pointer is a shape nothing in production creates.
    """

    def _grant(user, achievement, count=1):
        """Create ``count`` valid manual grants, one save each."""
        rows = []
        for _ in range(count):
            rows.append(
                UserAchievement.objects.create(
                    user=user, achievement=achievement, source_type=SourceType.MANUAL
                )
            )
        return rows

    return _grant
