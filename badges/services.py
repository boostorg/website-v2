"""Badge recalculation - the single source of truth for ``UserBadge`` state.

``recalculate_badges`` derives a user's badge tiers from the count of their
valid ``UserAchievement`` rows for a given achievement type. It both awards
(creates / re-earns) and revokes ``UserBadge`` rows so the
count-vs-threshold invariant always holds. It is idempotent: calling it
repeatedly with unchanged data produces no further writes.

No code outside this module (and the admin's direct-revocation action) should
write to ``UserBadge``.

It also owns ``discard_source_achievements``, the achievement-side write for
source rows that are about to be deleted outright.
"""

import logging

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone

from badges.enums import rank_order
from badges.models import (
    Achievement,
    Badge,
    BadgeTier,
    RevocationSource,
    UserAchievement,
    UserBadge,
)

logger = logging.getLogger(__name__)

CASCADE_REVOCATION_NOTE = (
    "Automatically revoked: valid achievement count for '{achievement}' fell "
    "below the threshold for this tier after an achievement was invalidated."
)


def discard_source_achievements(model, object_ids):
    """Delete automatic grants pointing at the given rows and recalculate.

    ``UserAchievement`` reaches its source through a generic foreign key, which
    carries no referential integrity, so hard-deleting a source row on its own
    leaves a grant that still counts toward a threshold. Call this *before*
    deleting anything a ``badges.sources`` iterator yields.
    """
    object_ids = list(object_ids)
    if not object_ids:
        return
    content_type = ContentType.objects.get_for_model(model)
    grants = UserAchievement.objects.filter(
        source_content_type=content_type, source_object_id__in=object_ids
    )
    pairs = set(grants.values_list("user_id", "achievement_id"))
    grants.delete()
    for user_id, achievement_id in pairs:
        recalculate_badges(user_id, achievement_id)


def deactivate_tier(tier, actor=None):
    """Retire a tier, recording who did it.

    A soft delete: the ``UserBadge`` rows that reference the tier are the record
    of why a member earned a badge, and they are deliberately preserved. Members
    who already reached the old threshold keep their badge - see
    ``badges.models.BadgeTier``.
    """
    if not tier.is_active:
        return
    tier.is_active = False
    tier.deactivated_at = timezone.now()
    tier.deactivated_by = actor
    tier.save(update_fields=["is_active", "deactivated_at", "deactivated_by"])


def reactivate_tier(tier):
    """Undo a retirement, refusing a rank that is already taken.

    ``full_clean`` runs ``BadgeTier.clean``, which enforces one active tier per
    (badge, rank), so an accidental retirement can be undone but a conflicting
    one raises ``ValidationError``.
    """
    if tier.is_active:
        return
    tier.is_active = True
    tier.deactivated_at = None
    tier.deactivated_by = None
    tier.full_clean()
    tier.save(update_fields=["is_active", "deactivated_at", "deactivated_by"])


def replace_tier(tier, actor=None):
    """Retire the stored tier and create its replacement.

    ``tier`` is an in-memory instance already carrying the new rank and
    threshold, while its row still holds the old values. Saving it would update
    the threshold in place, and the next recalculation would then revoke every
    member who only ever met the old one. Retiring and re-adding is what
    preserves them - see ``badges.models.BadgeTier``.

    Retiring first also keeps ``unique_active_badgetier_per_rank`` satisfied,
    which a threshold-only change would otherwise violate.
    """
    with transaction.atomic():
        stored = BadgeTier.objects.select_for_update().get(pk=tier.pk)
        deactivate_tier(stored, actor)
        replacement = BadgeTier.objects.create(
            badge_id=tier.badge_id, rank=tier.rank, threshold=tier.threshold
        )
    return stored, replacement


def achievement_pairs(achievement_ids=None, user_ids=None):
    """``(user_id, achievement_id)`` pairs worth recalculating.

    Both halves of the union matter. A pair whose achievements were all
    invalidated still has badges to revoke, and a pair whose achievements were
    hard-deleted without firing ``post_delete`` - a bulk delete, a data
    migration, raw SQL - leaves badges that nothing else will ever revisit.

    A UNION rather than two loops, so the database deduplicates the pairs and no
    caller has to hold the whole work list in memory.
    """
    grants = UserAchievement.objects.all()
    badges = UserBadge.objects.all()
    if achievement_ids is not None:
        grants = grants.filter(achievement_id__in=achievement_ids)
        badges = badges.filter(badge__achievement_id__in=achievement_ids)
    if user_ids is not None:
        grants = grants.filter(user_id__in=user_ids)
        badges = badges.filter(user_id__in=user_ids)
    return grants.values_list("user_id", "achievement_id").union(
        badges.values_list("user_id", "badge__achievement_id")
    )


def recalculate_many(pairs):
    """Recalculate every pair in ``pairs``; return how many were visited."""
    count = 0
    for user_id, achievement_id in pairs.iterator(chunk_size=1000):
        recalculate_badges(user_id, achievement_id)
        count += 1
    return count


@transaction.atomic
def recalculate_badges(user_id, achievement_id, *, acting_user=None):
    """Reconcile a user's ``UserBadge`` rows against one achievement type.

    Counts the user's valid ``UserAchievement`` rows for the achievement and,
    for every badge that this achievement feeds and every active tier of that
    badge:

    * awards (or re-earns) the tier when the count meets its threshold, and
    * revokes the tier when the count has fallen below its threshold.

    A rank *below* one the member already holds is never newly awarded. Retuning
    a threshold retires the old tier and adds a replacement, so shifting a whole
    ladder up by five leaves a gold holder meeting the new bronze threshold long
    before the new platinum one - and awarding them bronze would read as a
    demotion for a member who has only gained grants. Their next rung is
    platinum. A tier the member *already* has a row for is unaffected, so a
    cascade-revoked rank still comes back when its own count recovers.

    Args:
        user_id: Primary key of the user whose badges are being recalculated.
        achievement_id: Primary key of the ``Achievement`` whose count changed.
        acting_user: The admin responsible for a triggering invalidation, if
            any. Recorded as ``revoked_by`` on any cascade revocation.
    """
    # The achievement is fetched for the revocation note. The user is never
    # dereferenced, so an id whose row is gone simply counts zero achievements.
    achievement = Achievement.objects.filter(pk=achievement_id).first()
    if achievement is None:
        logger.warning(
            "Skipping badge recalculation: achievement %s is gone.", achievement_id
        )
        return

    valid_count = UserAchievement.objects.filter(
        user_id=user_id, achievement=achievement, is_valid=True
    ).count()

    badges = Badge.objects.filter(achievement=achievement).prefetch_related(
        Prefetch("tiers", queryset=BadgeTier.objects.filter(is_active=True))
    )
    # A tier belongs to exactly one badge, so tier_id alone identifies the row.
    # ``tier`` is joined for its rank, which decides how far up each ladder the
    # member already stands.
    held = {}
    # Highest rank held per badge, as a ladder position. -1 is "holds nothing",
    # which every rank outranks.
    floors = {}
    for user_badge in UserBadge.objects.filter(
        user_id=user_id, badge__achievement=achievement
    ).select_related("tier"):
        held[user_badge.tier_id] = user_badge
        if user_badge.is_active:
            floors[user_badge.badge_id] = max(
                floors.get(user_badge.badge_id, -1),
                rank_order(user_badge.tier.rank),
            )

    for badge in badges:
        floor = floors.get(badge.pk, -1)
        for tier in badge.tiers.all():
            user_badge = held.get(tier.pk)
            if valid_count < tier.threshold:
                if user_badge is not None and user_badge.is_active:
                    _revoke_tier(user_badge, achievement, acting_user)
            elif user_badge is not None or rank_order(tier.rank) > floor:
                _award_tier(badge, user_id, tier, user_badge)


def _award_tier(badge, user_id, tier, user_badge):
    """Create or re-earn a ``UserBadge`` whose threshold is met.

    A manual revocation is never undone here: a deliberate admin revocation must
    survive recalculation, and only the reinstate admin action brings it back.
    """
    if user_badge is None:
        # get_or_create: a concurrent recalculation (Celery task vs. signal)
        # may have inserted the row since the caller's lookup.
        user_badge, created = UserBadge.objects.get_or_create(
            badge=badge, user_id=user_id, tier=tier
        )
        if created:
            return
    if user_badge.revocation_source == RevocationSource.MANUAL:
        return
    if not user_badge.is_active:
        user_badge.revoked_at = None
        user_badge.revoked_by = None
        user_badge.revocation_notes = ""
        user_badge.revocation_source = ""
        user_badge.awarded_at = timezone.now()
        user_badge.save(
            update_fields=[
                "revoked_at",
                "revoked_by",
                "revocation_notes",
                "revocation_source",
                "awarded_at",
            ]
        )


def _revoke_tier(user_badge, achievement, acting_user):
    """Soft-revoke a ``UserBadge`` whose threshold is no longer met."""
    user_badge.revoked_at = timezone.now()
    user_badge.revoked_by = acting_user
    user_badge.revocation_notes = CASCADE_REVOCATION_NOTE.format(
        achievement=achievement
    )
    user_badge.revocation_source = RevocationSource.CASCADE
    user_badge.save(
        update_fields=[
            "revoked_at",
            "revoked_by",
            "revocation_notes",
            "revocation_source",
        ]
    )
