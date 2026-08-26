"""Tests for the badges Celery tasks."""

import pytest

from badges.models import AchievementSyncRun, SyncMode, SyncTrigger, UserAchievement
from badges.sources import AUTOMATIC_SLUGS
from badges.tasks import backfill_achievements_task, reconcile_achievements_task

pytestmark = pytest.mark.django_db


def test_backfill_task_sweeps_every_source_by_default(catalogue, capsys):
    """No argument is the whole database, which is what the weekly run wants."""
    backfill_achievements_task()

    output = capsys.readouterr().out
    for slug in AUTOMATIC_SLUGS:
        assert f"{slug}:" in output


def test_backfill_task_scopes_to_one_source(catalogue, capsys):
    """A slug reaches the command as ``--source`` rather than being ignored.

    The task passes it by the argument's ``dest``, a different word from the
    option, so the only proof it landed is one source running and the others not.
    """
    backfill_achievements_task(slug="library-authoring")

    output = capsys.readouterr().out
    assert "library-authoring:" in output
    assert "code-commits:" not in output


def test_reconcile_task_scopes_its_run_to_one_member(
    stale_commit_grant, commit_by_someone_else, plain_user, super_user
):
    """The wrappers are the only place the commands' option names are spelled.

    ``slug`` becomes ``slugs``, ``user_id`` becomes a one-element list of strings
    for the command's email-or-id resolution, and ``actor_id`` becomes both the
    run's actor and, through it, its trigger. A wrong name here is a TypeError
    inside a worker, on the path an admin reaches by hand from a member's page.

    Called for real rather than against a patched ``call_command``: asserting the
    forwarded keywords would pin the spelling without proving the command accepts
    it, which is the half that breaks.
    """
    reconcile_achievements_task(
        slug="code-commits", user_id=plain_user.pk, actor_id=super_user.pk
    )

    assert not UserAchievement.objects.filter(user=plain_user).exists()
    # Out of scope, so its stale-or-not is never considered.
    assert UserAchievement.objects.filter(user=super_user).exists()
    run = AchievementSyncRun.objects.get(mode=SyncMode.RECONCILE)
    assert run.source_slug == "code-commits"
    assert run.removed == 1
    assert run.triggered_by == super_user
    assert run.trigger == SyncTrigger.ADMIN
