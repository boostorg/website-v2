"""Badge recalculation - the single source of truth for ``UserBadge`` state.

``recalculate_badges`` derives a user's badge tiers from the count of their
valid ``UserAchievement`` rows for a given achievement type. It both awards
(creates / re-earns) and revokes ``UserBadge`` rows so the
count-vs-threshold invariant always holds. It is idempotent: calling it
repeatedly with unchanged data produces no further writes.

No code outside this module (and the admin's direct-revocation action) should
write to ``UserBadge``.

It also owns the achievement-side writes that feed it: ``sync_source``, which
makes the stored automatic grants for one source agree with that source in both
directions, and ``discard_source_achievements``, for source rows that are about to
be deleted outright.
"""

import logging
from typing import NamedTuple

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone

from badges import sources
from badges.enums import rank_order
from badges.models import (
    Achievement,
    Badge,
    BadgeTier,
    RevocationSource,
    SourceType,
    UserAchievement,
    UserBadge,
)

logger = logging.getLogger(__name__)

CASCADE_REVOCATION_NOTE = (
    "Automatically revoked: valid achievement count for '{achievement}' fell "
    "below the threshold for this tier after an achievement was invalidated."
)

# Rows per DELETE ... WHERE pk IN (...) and per bulk_create. The unmatched set can
# be as large as the achievement table, and one statement per million bound
# parameters is not a statement any database wants.
SYNC_BATCH_SIZE = 1000


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


class SourceSync(NamedTuple):
    """What syncing one source found, and what it was allowed to do about it.

    ``yielded`` counts the whole iterator, before any user scope is applied. That
    is what lets ``refused`` tell "this member authored no commits any more" apart
    from "the commits table read empty and something upstream is broken".

    ``changed`` is the members whose grants moved, which is what a caller
    recalculates. It is populated on a dry run too, where it says who *would*
    change and must not be recalculated.
    """

    slug: str
    yielded: int
    added: int
    removed: int
    changed: frozenset
    applied: bool
    refused: bool

    def describe(self):
        """One sentence about what this source's sync found.

        On the tuple rather than in each caller, so the commands' console lines and
        the admin's confirmation page cannot reach different conclusions about the
        same numbers.
        """
        if self.refused:
            return (
                f"REFUSED - the source yielded nothing, so {self.removed} grant(s) "
                "were left alone"
            )
        if not (self.added or self.removed):
            return f"nothing to change ({self.yielded} yielded by the source)"
        parts = []
        if self.added:
            parts.append(f"{'added' if self.applied else 'add'} {self.added}")
        if self.removed:
            parts.append(f"{'removed' if self.applied else 'remove'} {self.removed}")
        lead = "" if self.applied else "would "
        return (
            f"{lead}{' and '.join(parts)} grant(s) "
            f"across {len(self.changed)} member(s)"
        )


def sync_source(
    slug,
    achievement,
    *,
    user_ids=None,
    add=True,
    remove=True,
    dry_run=False,
    allow_empty=False,
    batch_size=SYNC_BATCH_SIZE,
):
    """Make the stored automatic grants for one source agree with that source.

    One walk of the iterator answers both halves of the question. A pair the
    source yields with no row behind it is missing and gets created; a row the
    source never yields is stale and gets deleted - a commit re-assigned to
    another author, a maintainer dropped from a library, a news entry
    unpublished. ``backfill_achievements`` is this with ``remove=False``, which is
    why it cannot undo anything, and why the weekly pipeline is safe to point at
    it.

    Manual grants are never touched. Only ``source_type=AUTOMATIC`` rows are
    considered, which is also why an automatic row with no source pointer counts
    as stale: nothing in this codebase can create one, it cannot be matched
    against anything an iterator yields, and this is the right place to clear it.
    An *invalidated* automatic row is matched like any other, so an admin's
    judgement that a grant was wrong is never overwritten by a re-add.

    Stale grants are **deleted, not invalidated**, because
    ``unique_automatic_user_achievement_source`` does not include ``is_valid``:
    an invalidated row would permanently block this function from re-creating
    that grant if the attribution ever came back.

    Badges are **not** recalculated here. The caller owns that, because it knows
    whether it is looking at one member or the whole table, and because on a dry
    run there is nothing to recalculate. ``recalculate_on_achievement_delete``
    does fire per deleted row, so removals partly recalculate themselves - see
    the note on ``changed``.

    Args:
        slug: A key of ``sources.BACKFILL_ITERATORS``.
        achievement: The ``Achievement`` that ``slug`` feeds.
        user_ids: Restrict both halves to these members. The iterator is still
            walked in full - there is no way to ask it about one member - but no
            other member's grants are created or deleted.
        add: Create the grants the source yields and the database is missing.
        remove: Delete the stored grants the source did not yield.
        dry_run: Report what would change, writing nothing.
        allow_empty: Delete even when the iterator yielded nothing at all. Off by
            default: see ``refused`` below.
        batch_size: Rows per ``bulk_create`` and per ``DELETE ... IN``.

    Returns:
        A ``SourceSync``. ``refused`` is set when the iterator yielded no pairs
        while stale grants exist, which is indistinguishable from a broken source
        and would otherwise revoke every badge the source feeds. Nothing is
        deleted in that case unless ``allow_empty`` says so; the additive half is
        unaffected, there being nothing to add.
    """
    stored = UserAchievement.objects.filter(
        achievement=achievement, source_type=SourceType.AUTOMATIC
    )
    if user_ids is not None:
        stored = stored.filter(user_id__in=user_ids)

    # Every stored key, keyed by what the iterator can reconstruct and valued by
    # the rows carrying it. Whatever survives the walk is stale, and a key the
    # walk cannot find here is a grant that does not exist yet - so one dict
    # answers both halves and the walk needs no per-batch lookup of its own.
    # Bounded by this achievement's row count rather than by the source's, so a
    # scoped run holds one member's grants in memory and not every commit.
    #
    # A list of rows per key, not one: the source pointer is nullable, so several
    # automatic rows can share ``(user, NULL, NULL)``, and one slot per key would
    # clear all but the last of them per run. A key with a real pointer can only
    # ever hold one row - ``unique_automatic_user_achievement_source`` says so.
    unmatched = {}
    for pk, user_id, content_type_id, object_id in stored.values_list(
        "pk", "user_id", "source_content_type_id", "source_object_id"
    ).iterator(chunk_size=2000):
        unmatched.setdefault((user_id, content_type_id, object_id), []).append(pk)

    scope = None if user_ids is None else set(user_ids)
    yielded = added = 0
    changed = set()
    pending = {}

    def flush():
        """Insert the batch built so far and count it as added."""
        nonlocal added, pending
        if not pending:
            return
        if not dry_run:
            # ignore_conflicts because ``unmatched`` is a snapshot: a concurrent
            # run of this same function may have inserted the row since.
            UserAchievement.objects.bulk_create(
                list(pending.values()), ignore_conflicts=True
            )
        added += len(pending)
        pending = {}

    for user, source in sources.BACKFILL_ITERATORS[slug]():
        yielded += 1
        # The scope is applied here as well as on ``unmatched``: an out-of-scope
        # member's key is absent from it, which on the additive side is
        # indistinguishable from a grant that needs creating.
        if scope is not None and user.pk not in scope:
            continue
        content_type = ContentType.objects.get_for_model(source)
        key = (user.pk, content_type.pk, source.pk)
        if unmatched.pop(key, None) is not None:
            continue
        # ``pending`` is keyed, so an iterator that yields the same pair twice
        # inside one batch counts it once. Across a flush the unique constraint
        # is what catches it, and only the count is then optimistic.
        if not add or key in pending:
            continue
        changed.add(user.pk)
        pending[key] = UserAchievement(
            user_id=user.pk,
            achievement=achievement,
            source_type=SourceType.AUTOMATIC,
            source_content_type=content_type,
            source_object_id=source.pk,
        )
        if len(pending) >= batch_size:
            flush()
    flush()

    stale = [pk for pks in unmatched.values() for pk in pks] if remove else []
    if stale and not yielded and not allow_empty:
        logger.warning(
            "Refusing to remove %s stale grant(s) for '%s': the source yielded "
            "nothing at all. Pass allow_empty to override.",
            len(stale),
            slug,
        )
        return SourceSync(
            slug, yielded, added, len(stale), frozenset(changed), not dry_run, True
        )

    if remove:
        changed.update(user_id for user_id, _, _ in unmatched)

    if stale and not dry_run:
        # Not one transaction: each chunk leaves the badge state consistent with
        # the grants that survive it, so a run that dies half way through is
        # simply a run to repeat, not one to unwind.
        for start in range(0, len(stale), batch_size):
            UserAchievement.objects.filter(
                pk__in=stale[start : start + batch_size]
            ).delete()

    return SourceSync(
        slug, yielded, added, len(stale), frozenset(changed), not dry_run, False
    )


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
