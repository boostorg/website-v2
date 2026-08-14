"""Signals that keep badge state in step with achievement and tier changes.

Creating, invalidating or deleting a ``UserAchievement`` all move a member's valid
count, so all three funnel into ``recalculate_badges``.

A ``BadgeTier`` change affects every member of that achievement type, so it goes
to a task instead of the request. It can only ever add badges: recalculation
revokes against active tiers only, and a retired tier's badges are preserved.
"""

from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from badges.models import Badge, BadgeTier, UserAchievement
from badges.services import recalculate_badges
from badges.tasks import recalculate_achievement_task


@receiver(post_save, sender=UserAchievement)
def recalculate_on_achievement_save(sender, instance, created, raw, **kwargs):
    """Recalculate when an achievement is created or invalidated.

    An invalidating save forwards ``invalidated_by`` so a cascade revocation is
    attributed to the admin who caused it.
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
    """Recalculate when an achievement row is hard-deleted."""
    recalculate_badges(instance.user_id, instance.achievement_id)


@receiver([post_save, post_delete], sender=BadgeTier)
def recalculate_on_tier_change(sender, instance, **kwargs):
    """Revisit an achievement when one of its tiers is added, retired or removed.

    Deferred to commit because the admin wraps the change form in a transaction,
    and a worker picking the job up early would read pre-commit state.
    """
    if kwargs.get("raw"):
        return

    achievement_id = (
        Badge.objects.filter(pk=instance.badge_id)
        .values_list("achievement_id", flat=True)
        .first()
    )
    # Defence against a delete that did not go through the ORM. A cascade deletes
    # tiers before their badge, so the badge is normally still readable here.
    if achievement_id is None:
        return

    transaction.on_commit(lambda: recalculate_achievement_task.delay(achievement_id))
