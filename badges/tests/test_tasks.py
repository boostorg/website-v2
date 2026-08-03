"""Tests for the badges Celery tasks."""

import pytest

from badges.sources import AUTOMATIC_SLUGS
from badges.tasks import backfill_achievements_task

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
