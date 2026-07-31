"""Signals that keep badge state in sync with achievement and tier changes.

Creating a ``UserAchievement``, invalidating one (a soft update to ``is_valid``)
and hard-deleting one all change a member's valid count, so all three funnel into
``recalculate_badges``.

A ``BadgeTier`` change instead affects *every* member of that achievement type, so
it goes through a task rather than the request. It can only ever add badges:
``recalculate_badges`` revokes only against an active tier's threshold, and a
retired tier's badges are deliberately preserved, so grandfathering survives.
"""

from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from badges.models import Badge, BadgeTier, UserAchievement
from badges.services import recalculate_badges
from badges.tasks import recalculate_achievement_task


@receiver(post_save, sender=UserAchievement)
def recalculate_on_achievement_save(sender, instance, created, raw, **kwargs):
    """Recalculate badges when an achievement is created or invalidated.

    When the save invalidated the achievement, the admin who performed the
    invalidation (``invalidated_by``) is forwarded so any cascade badge
    revocation is correctly attributed.
    """
    if raw:
        return

    acting_user = None if instance.is_valid else instance.invalidated_by
    recalculate_badges(
        instance.user_id,
        instance.achievement_id,
        acting_user=acting_user,
    )


@receiver(post_delete, sender=UserAchievement)
def recalculate_on_achievement_delete(sender, instance, **kwargs):
    """Recalculate badges when an achievement row is hard-deleted."""
    recalculate_badges(instance.user_id, instance.achievement_id)


@receiver([post_save, post_delete], sender=BadgeTier)
def recalculate_on_tier_change(sender, instance, **kwargs):
    """Revisit an achievement when one of its tiers is added, retired or removed.

    Deferred to commit because the admin wraps the change form in a transaction:
    a worker that picked the job up early would read pre-commit state.
    """
    if kwargs.get("raw"):
        return

    achievement_id = (
        Badge.objects.filter(pk=instance.badge_id)
        .values_list("achievement_id", flat=True)
        .first()
    )
    if achievement_id is None:  # the badge cascaded away with the tier
        return

    transaction.on_commit(lambda: recalculate_achievement_task.delay(achievement_id))
