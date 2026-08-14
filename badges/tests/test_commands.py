"""Tests for the recalculate_badges management command."""

import pytest
from django.core.management import call_command

from badges.enums import AchievementSlug
from badges.models import (
    Achievement,
    SourceType,
    UserAchievement,
    UserBadge,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _catalogue(catalogue):
    """Seed the real achievement catalogue for every test in this module."""


def _grant(user, slug):
    """One valid manual grant, which is all a threshold of 1 needs.

    Built directly rather than through a source iterator: recalculation reads
    ``UserAchievement`` rows and does not care where they came from.
    """
    return UserAchievement.objects.create(
        user=user,
        achievement=Achievement.objects.get(slug=slug),
        source_type=SourceType.MANUAL,
    )


def test_recalculate_rebuilds_badges(plain_user):
    """The recalculate command restores badge rows from achievement counts."""
    _grant(plain_user, AchievementSlug.LIBRARY_AUTHORING)
    UserBadge.objects.all().delete()  # wipe derived state

    call_command("recalculate_badges")

    assert UserBadge.objects.filter(
        user=plain_user,
        badge__achievement__slug=AchievementSlug.LIBRARY_AUTHORING,
    ).exists()


def test_recalculate_revokes_when_every_achievement_is_invalid(plain_user):
    """A pair with no valid achievements left must still be recalculated.

    ``update()`` skips the post_save signal, mimicking data fixed outside the
    admin - exactly the case this command exists to repair.
    """
    _grant(plain_user, AchievementSlug.LIBRARY_AUTHORING)
    UserAchievement.objects.filter(user=plain_user).update(is_valid=False)
    assert UserBadge.objects.filter(user=plain_user, revoked_at=None).exists()

    call_command("recalculate_badges")

    assert not UserBadge.objects.filter(user=plain_user, revoked_at=None).exists()


def test_recalculate_revokes_badges_whose_achievements_are_gone(plain_user):
    """A badge orphaned by a signal-free delete is revoked, not left standing.

    Bulk deletes, data migrations and raw SQL never fire ``post_delete``, so the
    full recalculation is the only thing that can clean up after them.
    """
    _grant(plain_user, AchievementSlug.LIBRARY_REVIEW)
    badge = UserBadge.objects.get(user=plain_user)
    assert badge.revoked_at is None

    # Delete the rows the way a bulk path would: no post_delete receivers run.
    UserAchievement.objects.filter(user=plain_user)._raw_delete(using="default")

    call_command("recalculate_badges")

    badge.refresh_from_db()
    assert badge.revoked_at is not None
