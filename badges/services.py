"""Badge recalculation - the only writer of ``UserBadge`` state.

``recalculate_badges`` derives a member's tiers from their count of valid
``UserAchievement`` rows. It awards and revokes, so the count-vs-threshold
invariant always holds, and it is idempotent.

Concurrent runs for the same (user, achievement) are not serialised: two
overlapping recalculations can leave the badge reflecting the earlier of their
two counts. Any later event for the pair, or a full ``recalculate_badges`` run,
repairs it.
"""

import contextvars
import logging
from contextlib import contextmanager

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
    "Automatically revoked: {count} valid '{achievement}' achievement(s), below "
    "the {rank} threshold of {threshold}."
)

_revocation_cause = contextvars.ContextVar("badge_revocation_cause", default=None)


@contextmanager
def revocation_cause(description):
    """Name what is about to change achievement counts, for the audit trail.

    A cascade revocation records only arithmetic, which tells support that a
    count fell but not what moved it. Anything that changes grants in bulk should
    wrap the work in this so the note says which operation was responsible.
    """
    token = _revocation_cause.set(description)
    try:
        yield
    finally:
        _revocation_cause.reset(token)


def discard_source_achievements(model, object_ids):
    """Delete automatic grants pointing at the given rows and recalculate.

    A grant reaches its source through a generic foreign key, which carries no
    referential integrity, so deleting a source row on its own leaves a grant
    still counting toward a threshold. Call this first.

    The caller is expected to own the transaction.
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

    A soft delete, so the badges already awarded against the tier are preserved
    and members who met the old threshold keep them.
    """
    if not tier.is_active:
        return
    tier.is_active = False
    tier.deactivated_at = timezone.now()
    tier.deactivated_by = actor
    tier.save(update_fields=["is_active", "deactivated_at", "deactivated_by"])


def reactivate_tier(tier):
    """Undo a retirement, refusing a taken rank or an out-of-order threshold.

    ``full_clean`` runs ``BadgeTier.clean``, so an accidental retirement can be
    undone while a conflicting one raises ``ValidationError``.
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

    ``tier`` is an in-memory instance carrying the new values while its row still
    holds the old ones. Saving it would update the threshold in place, and the
    next recalculation would revoke everyone who only ever met the old number.
    Retiring first also keeps the one-active-tier-per-rank constraint satisfied.
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

    Both halves of the union matter: a pair whose grants were all invalidated
    still has badges to revoke, and grants deleted without firing ``post_delete``
    leave badges nothing else would revisit. A UNION so the database deduplicates
    and no caller holds the work list in memory.
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
    """Reconcile a member's ``UserBadge`` rows against one achievement type.

    For every active tier of every badge the achievement feeds, awards the tier
    when the count meets its threshold and revokes it when the count has fallen
    below.

    A rank *below* one the member already holds is never newly awarded. Shifting a
    ladder up leaves a gold holder meeting the new bronze long before the new
    platinum, and awarding bronze would read as a demotion for someone who has
    only gained grants. A tier they already have a row for is exempt, so a
    cascade-revoked rank still returns when its own count recovers.

    Args:
        user_id: Whose badges to recalculate.
        achievement_id: The ``Achievement`` whose count changed.
        acting_user: The admin behind a triggering invalidation, recorded as
            ``revoked_by`` on any cascade revocation.
    """
    # The user is never dereferenced, so an id whose row is gone counts zero.
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
    # A tier belongs to one badge, so tier_id alone identifies the row. ``tier``
    # is joined for its rank, which fixes how far up the ladder the member stands.
    held = {}
    # Highest rank held per badge. -1 is "holds nothing", which every rank beats.
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
                    _revoke_tier(user_badge, achievement, valid_count, acting_user)
            elif user_badge is not None or rank_order(tier.rank) > floor:
                _award_tier(badge, user_id, tier, user_badge)


def _award_tier(badge, user_id, tier, user_badge):
    """Create or re-earn a ``UserBadge`` whose threshold is met.

    A manual revocation is never undone here: a deliberate admin revocation must
    survive recalculation, and only the reinstate admin action brings it back.
    """
    if user_badge is None:
        # get_or_create: a concurrent recalculation may have inserted the row
        # since the caller looked.
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
        user_badge.count_at_revocation = None
        user_badge.awarded_at = timezone.now()
        user_badge.save(
            update_fields=[
                "revoked_at",
                "revoked_by",
                "revocation_notes",
                "revocation_source",
                "count_at_revocation",
                "awarded_at",
            ]
        )


def _revoke_tier(user_badge, achievement, valid_count, acting_user):
    """Soft-revoke a ``UserBadge`` whose threshold is no longer met.

    The note carries the arithmetic, and the cause when a caller has named one.
    Without both, support can see that a badge went away but not why.
    """
    note = CASCADE_REVOCATION_NOTE.format(
        count=valid_count,
        achievement=achievement,
        rank=user_badge.tier.get_rank_display(),
        threshold=user_badge.tier.threshold,
    )
    cause = _revocation_cause.get()
    if cause:
        note = f"{note} Cause: {cause}."

    user_badge.revoked_at = timezone.now()
    user_badge.revoked_by = acting_user
    user_badge.revocation_notes = note
    user_badge.revocation_source = RevocationSource.CASCADE
    user_badge.count_at_revocation = valid_count
    user_badge.save(
        update_fields=[
            "revoked_at",
            "revoked_by",
            "revocation_notes",
            "revocation_source",
            "count_at_revocation",
        ]
    )
