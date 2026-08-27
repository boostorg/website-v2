"""Background page conversion work.

The command wrappers exist so the admin changelist buttons can start a long-running
command on a worker instead of holding the request open.
"""

import logging

from celery import shared_task
from django.core.management import call_command

logger = logging.getLogger(__name__)


@shared_task
def backfill_achievements_task():
    """
    Run the `convert_news_entries` management command as a one-off request.

    Fundamentally indopetent, this command can be run several times without causing a problem
    so long as entries are still the source of truth (aka post launch)
    """
    call_command("convert_news_entries")


@shared_task
def update_index_task():
    """
    Run the 'update_index' management command as a one-off request.

    Needs to be run after the convert_news_entry task is run in order to ensure wagtail indexing
    is up to date for searching
    """
    call_command("update_index")
