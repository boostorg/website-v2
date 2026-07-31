"""Background badge work.

``recalculate_achievement_task`` is narrow on purpose: a configuration change
only affects the members of one achievement type, so there is no reason to sweep
the table - and no reason to make the request that changed it wait either.
"""

from celery import shared_task

from badges.services import achievement_pairs, recalculate_many


@shared_task
def recalculate_achievement_task(achievement_id):
    """Recalculate every (user, achievement) pair for one achievement type."""
    return recalculate_many(achievement_pairs([achievement_id]))
