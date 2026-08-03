"""Tests for the sync run log, the record a revoked badge points at."""

import pytest
from django.core.management import call_command
from model_bakery import baker

from badges.admin import reconcile_apply, reconcile_preview
from badges.models import (
    AchievementSyncRun,
    SyncMode,
    SyncTrigger,
    UserAchievement,
    UserBadge,
)

pytestmark = pytest.mark.django_db

SOURCE = "code-commits"


@pytest.fixture(autouse=True)
def _catalogue(catalogue):
    """Seed the real achievement catalogue for every test in this module."""


def _commit(user):
    """One commit attributed to ``user``, which the badge counts."""
    author = baker.make("libraries.CommitAuthor", user=user)
    return baker.make("libraries.Commit", author=author)


def test_a_backfill_is_recorded(plain_user):
    """Every real run leaves a row saying what it did."""
    _commit(plain_user)

    call_command("backfill_achievements", "--source", SOURCE)

    run = AchievementSyncRun.objects.get(source_slug=SOURCE)
    assert run.mode == SyncMode.BACKFILL
    assert run.trigger == SyncTrigger.COMMAND
    assert run.added == 1
    assert run.removed == 0
    assert run.members_changed == 1
    assert run.finished_at is not None


def test_a_reconcile_is_recorded_as_such(plain_user):
    """The mode distinguishes the run that can delete from the one that cannot."""
    call_command("reconcile_achievements", "--source", SOURCE)

    assert AchievementSyncRun.objects.get(source_slug=SOURCE).mode == SyncMode.RECONCILE


def test_the_trigger_records_the_release_pipeline(plain_user):
    """Whether a person or the weekly job did this is the first thing support asks."""
    _commit(plain_user)

    call_command(
        "backfill_achievements", "--source", SOURCE, "--trigger", SyncTrigger.PIPELINE
    )

    assert (
        AchievementSyncRun.objects.get(source_slug=SOURCE).trigger
        == SyncTrigger.PIPELINE
    )


def test_an_admin_reconcile_records_who_ran_it(plain_user, super_user):
    """A reconcile started from the admin names the admin who started it."""
    reconcile_apply([SOURCE], actor=super_user)

    run = AchievementSyncRun.objects.get(source_slug=SOURCE)
    assert run.trigger == SyncTrigger.ADMIN
    assert run.triggered_by == super_user


def test_a_dry_run_is_not_recorded(plain_user):
    """A preview writes nothing, and the confirmation page previews on every open."""
    _commit(plain_user)

    reconcile_preview([SOURCE])

    assert not AchievementSyncRun.objects.exists()


def test_a_revoked_badge_names_the_run_that_removed_its_grants(plain_user):
    """The whole point: from a lost badge to the operation that caused it."""
    commit = _commit(plain_user)
    # Somebody else's commit, so the source is not empty afterwards: an iterator
    # that yields nothing at all is refused rather than believed.
    _commit(baker.make("users.User", email="other-committer@example.com"))
    call_command("backfill_achievements", "--source", SOURCE)
    assert UserBadge.objects.filter(user=plain_user, revoked_at=None).exists()

    # The upstream correction: the commit history this badge rested on is gone.
    commit.delete()
    call_command("reconcile_achievements", "--source", SOURCE)

    assert not UserAchievement.objects.filter(user=plain_user).exists()
    revoked = UserBadge.objects.get(user=plain_user, revoked_at__isnull=False)
    run = AchievementSyncRun.objects.get(source_slug=SOURCE, mode=SyncMode.RECONCILE)
    assert f"#{run.pk}" in revoked.revocation_notes
    assert revoked.count_at_revocation == 0
    assert run.removed == 1


def test_a_refused_run_records_that_it_removed_nothing(plain_user):
    """A source reading empty is logged as refused, not as a successful no-op."""
    commit = _commit(plain_user)
    call_command("backfill_achievements", "--source", SOURCE)
    # Every commit gone at once is what a broken import looks like, not a member
    # who stopped contributing.
    baker.make("libraries.Commit", author=commit.author).delete()
    commit.delete()

    call_command("reconcile_achievements", "--source", SOURCE)

    run = AchievementSyncRun.objects.filter(mode=SyncMode.RECONCILE).latest(
        "started_at"
    )
    assert run.refused is True
    assert run.removed == 0
    assert UserAchievement.objects.filter(user=plain_user).exists()
