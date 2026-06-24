"""Shared fixtures and helpers for the badges tests.

Registered as a pytest plugin in the root ``conftest.py``, so the fixtures here
are available everywhere; the plain helpers have to be imported.
"""

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from model_bakery import baker

from badges.catalogue import seed_catalogue
from badges.enums import BadgeLabel, TierRank
from badges.models import (
    Achievement,
    Badge,
    BadgeTier,
    SourceType,
    UserAchievement,
    UserBadge,
)
from badges.services import replace_tier

# The user's ladder from the bug report: one achievement per rank, so every rung
# is one grant above the last and a shift moves all five together.
ONE_PER_RANK = {
    TierRank.BRONZE: 1,
    TierRank.SILVER: 2,
    TierRank.GOLD: 3,
    TierRank.PLATINUM: 4,
    TierRank.DIAMOND: 5,
}


def grant_from_source(user, achievement, source):
    """Record an automatic grant pointing at ``source``, the way a backfill does.

    ``backfill_achievements`` writes these in bulk, which is unusable for a test
    that needs one row and its generic foreign key. ``get_or_create`` rather than
    ``create`` so a test can also assert that a repeat is a no-op, which is what
    ``unique_automatic_user_achievement_source`` is there to guarantee.
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

    The ``badge`` fixture stops at gold, which is enough for most tests but cannot
    express "the rank above the one I hold" for a gold holder. Safe to call before
    any badge has been awarded, which is the only time it is used.
    """
    badge.tiers.all().delete()
    return [
        baker.make(BadgeTier, badge=badge, rank=rank, threshold=threshold)
        for rank, threshold in thresholds.items()
    ]


def shift_ladder(badge, by):
    """Add ``by`` to every active threshold, the way the badge admin page does.

    Goes through ``replace_tier`` rather than updating in place, so it leaves the
    shape a real retuning leaves: the old tiers retired with the badges awarded
    against them intact, and new active tiers carrying the new numbers.
    """
    for tier in list(badge.tiers.filter(is_active=True)):
        tier.threshold += by
        replace_tier(tier)


def active_ranks(user, badge):
    """The ranks of ``badge`` the user currently holds, read from the database.

    A plain helper rather than a fixture: it is called repeatedly inside a single
    test, before and after the thing under test, which is the whole point.
    """
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
    """A maintainer badge with bronze/silver/gold tiers (1/3/5)."""
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
def commit_by_someone_else(catalogue, super_user):
    """A live attributed commit belonging to another member, already recorded.

    ``sync_source`` refuses to act on a source that yields nothing at all, so a
    test about one member's stale grants has to leave the source yielding somebody.
    Only the tests of the refusal itself do without this.

    Backfilled, so this member is fully *in step* with the source: otherwise a
    two-way run would have a grant to create here, and every test using this
    fixture would be quietly asserting against that as well.
    """
    author = baker.make("libraries.CommitAuthor", user=super_user)
    commit = baker.make("libraries.Commit", author=author)
    call_command("backfill_achievements", "--source", "code-commits")
    return commit


@pytest.fixture
def stale_commit_grant(catalogue, plain_user):
    """Give ``plain_user`` a commits achievement, then break its attribution.

    Reproduces what reconciliation exists for: the ``Commit`` row survives, the
    ``UserAchievement`` row survives, and the two no longer agree because the
    ``CommitAuthor`` stopped pointing at the member. Returns the commit.
    """
    author = baker.make("libraries.CommitAuthor", user=plain_user)
    commit = baker.make("libraries.Commit", author=author)
    call_command("backfill_achievements", "--source", "code-commits")
    assert UserBadge.objects.filter(user=plain_user, revoked_at=None).exists()

    author.user = None
    author.save()
    return commit


@pytest.fixture
def grant_achievement(db):
    """Return a helper that creates valid UserAchievement rows.

    Manual, which is what these rows have always been called and now also what
    they are. The field defaults to automatic, and an *automatic* row with no
    source pointer is a shape nothing in production can produce and one
    ``sync_source`` classifies as stale - so a threshold test built on them was
    quietly asserting against garbage rows.
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
