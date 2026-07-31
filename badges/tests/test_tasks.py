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
