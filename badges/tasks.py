"""Background badge work.

The two command wrappers exist so the admin changelist buttons can start a
long-running command on a worker instead of holding the request open.
``recalculate_achievement_task`` is narrower: a configuration change only affects
the members of one achievement type, so there is no reason to sweep the table.
"""

from celery import shared_task
from django.core.management import call_command

from badges.services import achievement_pairs, recalculate_many


@shared_task
def backfill_achievements_task(slug=None):
    """Run the ``backfill_achievements`` management command off-request.

    No slug sweeps every wired source, which is what the weekly pipeline and the
    unscoped admin button want. A slug narrows the run to that one source, so a
    newly wired iterator can be backfilled without walking every commit in the
    database again.
    """
    if slug is None:
        call_command("backfill_achievements")
    else:
        call_command("backfill_achievements", slugs=[slug])


@shared_task
def recalculate_all_badges_task():
    """Run the ``recalculate_badges`` management command off-request."""
    call_command("recalculate_badges")


@shared_task
def reconcile_achievements_task(slug=None, user_id=None):
    """Run the ``reconcile_achievements`` command off-request.

    ``--allow-empty`` is deliberately not reachable from here. A source that reads
    empty is refused, and overriding that refusal is a decision for someone at a
    shell who has looked at why it is empty, not for a button.
    """
    options = {}
    if slug:
        options["slugs"] = [slug]
    if user_id:
        # A string because that is what argparse would have handed the command,
        # and what its email-or-id resolution expects.
        options["users"] = [str(user_id)]
    call_command("reconcile_achievements", **options)


@shared_task
def recalculate_achievement_task(achievement_id):
    """Recalculate every (user, achievement) pair for one achievement type."""
    return recalculate_many(achievement_pairs([achievement_id]))
