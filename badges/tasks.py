"""Background badge work.

``recalculate_achievement_task`` is narrow on purpose: a configuration change only
affects one achievement type, so there is no reason to sweep the whole table, and
no reason to make the request that changed it wait.
"""

import logging

from celery import shared_task

from badges.services import achievement_pairs, recalculate_many

logger = logging.getLogger(__name__)


@shared_task
def recalculate_achievement_task(achievement_id):
    """Recalculate every (user, achievement) pair for one achievement type."""
    count = recalculate_many(achievement_pairs([achievement_id]))
    logger.info("Recalculated %s pair(s) for achievement %s.", count, achievement_id)
    return count
