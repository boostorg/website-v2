"""Tests for the sync run log, the record a revoked badge points at."""

import re
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from model_bakery import baker

from badges import sources
from badges.admin import reconcile_apply, reconcile_preview
from badges.models import (
    AchievementSyncRun,
    SyncMode,
    SyncTrigger,
    UserAchievement,
    UserBadge,
)
from badges.tasks import backfill_achievements_task, reconcile_achievements_task

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


@pytest.mark.parametrize(
    "task,mode",
    [
        (backfill_achievements_task, SyncMode.BACKFILL),
        (reconcile_achievements_task, SyncMode.RECONCILE),
    ],
)
def test_a_run_started_from_a_button_names_who_pressed_it(super_user, task, mode):
    """The button hands its task the caller, which has to survive the trip.

    Both changelist buttons run on a worker, so the request the admin made is over
    long before the log row is written. Without the id travelling with the job, the
    two paths that do the most damage are the two the log cannot attribute.
    """
    task(slug=SOURCE, actor_id=super_user.pk)

    run = AchievementSyncRun.objects.get(source_slug=SOURCE, mode=mode)
    assert run.trigger == SyncTrigger.ADMIN
    assert run.triggered_by == super_user


def test_an_explicit_trigger_beats_the_one_an_actor_implies(plain_user, super_user):
    """A caller that states its trigger keeps it, actor or no actor."""
    _commit(plain_user)

    call_command(
        "backfill_achievements",
        "--source",
        SOURCE,
        "--trigger",
        SyncTrigger.PIPELINE,
        "--triggered-by",
        str(super_user.pk),
    )

    run = AchievementSyncRun.objects.get(source_slug=SOURCE)
    assert run.trigger == SyncTrigger.PIPELINE
    assert run.triggered_by == super_user


def test_a_run_whose_actor_no_longer_exists_still_happens(plain_user):
    """Attribution is worth less than the sweep it describes."""
    _commit(plain_user)

    call_command(
        "backfill_achievements", "--source", SOURCE, "--triggered-by", "123456789"
    )

    run = AchievementSyncRun.objects.get(source_slug=SOURCE)
    assert run.triggered_by is None
    assert run.added == 1


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
    second = baker.make("libraries.Commit", author=commit.author)
    call_command("backfill_achievements", "--source", SOURCE)
    assert UserAchievement.objects.filter(user=plain_user).count() == 2
    # Every commit gone at once is what a broken import looks like, not a member
    # who stopped contributing. Both grants are stale, and the refusal has to hold
    # for all of them rather than for the last one walked.
    second.delete()
    commit.delete()

    call_command("reconcile_achievements", "--source", SOURCE)

    run = AchievementSyncRun.objects.filter(mode=SyncMode.RECONCILE).latest(
        "started_at"
    )
    assert run.refused is True
    assert run.removed == 0
    assert UserAchievement.objects.filter(user=plain_user).count() == 2


def test_a_run_that_dies_part_way_is_recorded_as_failed(plain_user):
    """A crashed run must not read as one still in flight.

    The counts cannot say it: a run that died before writing anything looks exactly
    like a run with nothing to do. Since the deletes are chunked, a half-finished
    reconcile has already revoked badges that this row is the only record of.
    """
    commit = _commit(plain_user)

    def half_a_walk():
        yield plain_user, commit
        raise RuntimeError("the source went away")

    with patch.dict(sources.BACKFILL_ITERATORS, {SOURCE: half_a_walk}):
        # Re-raised rather than swallowed, so the command still exits non-zero and
        # a task still fails instead of reporting a clean run.
        with pytest.raises(RuntimeError):
            call_command("backfill_achievements", "--source", SOURCE)

    run = AchievementSyncRun.objects.get(source_slug=SOURCE)
    assert run.error == "RuntimeError: the source went away"
    assert run.finished_at is not None
    assert run.added == 0
    assert run.refused is False


def _flags(client, super_user):
    """The two flag icons of the single run on the changelist, in column order."""
    client.force_login(super_user)
    body = client.get(reverse("admin:badges_achievementsyncrun_changelist")).content
    return re.findall(rb"icon-(yes|no|unknown)\.svg", body)


@pytest.mark.parametrize(
    "finished_at,error,refused,expected",
    [
        (True, "", False, [b"yes", b"yes"]),
        (True, "RuntimeError: the source went away", False, [b"yes", b"no"]),
        (True, "", True, [b"no", b"yes"]),
        (False, "", False, [b"yes", b"unknown"]),
    ],
    ids=["clean", "died", "refused", "in-flight"],
)
def test_the_log_shows_a_tick_for_the_run_that_went_well(
    client, super_user, finished_at, error, refused, expected
):
    """Stored as the exception, read as the norm.

    The fields say ``refused`` and ``error``, so a run that did exactly what it was
    asked used to be two red crosses - the icon an admin scanning for trouble stops
    on. A run still in flight is the third state the pair of booleans could not
    express: it has no error only because it has not finished.
    """
    baker.make(
        AchievementSyncRun,
        source_slug=SOURCE,
        mode=SyncMode.BACKFILL,
        finished_at=timezone.now() if finished_at else None,
        error=error,
        refused=refused,
    )

    assert _flags(client, super_user) == expected
