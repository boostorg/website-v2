"""Badge recalculation - the only writer of ``UserBadge`` state.

``recalculate_badges`` derives a member's tiers from their count of valid
``UserAchievement`` rows. It awards and revokes, so the count-vs-threshold
invariant always holds, and it is idempotent.

Concurrent runs for the same (user, achievement) are not serialised: two
overlapping recalculations can leave the badge reflecting the earlier of their two
counts. Any later event for the pair, or a full ``recalculate_badges`` run, repairs
it.

This module also owns the achievement-side writes that feed recalculation:
``sync_source``, which makes the stored automatic grants for one source agree with
that source in both directions, and ``discard_source_achievements``, for source
rows about to be deleted outright.

Both delete in bulk, and both recalculate their own members rather than leaving it
to the ``post_delete`` signal, which fires per row: see ``owns_recalculation``.
"""

import contextvars
import logging
from contextlib import contextmanager
from typing import NamedTuple

from django.contrib.contenttypes.models import ContentType
from django.db import DatabaseError, transaction
from django.db.models import Prefetch
from django.utils import timezone

from badges import sources
from badges.enums import rank_order
from badges.models import (
    Achievement,
    AchievementSyncRun,
    Badge,
    BadgeTier,
    RevocationSource,
    SourceType,
    SyncMode,
    SyncTrigger,
    UserAchievement,
    UserBadge,
)

logger = logging.getLogger(__name__)

CASCADE_REVOCATION_NOTE = (
    "Automatically revoked: {count} valid '{achievement}' achievement(s), below "
    "the {rank} threshold of {threshold}."
)

# Rows per DELETE ... WHERE pk IN (...) and per bulk_create. The unmatched set can
# be as large as the achievement table.
SYNC_BATCH_SIZE = 1000

# A database error carries the statement that failed, which for a batch of a
# thousand rows is the whole batch. Enough to identify the fault, not the payload.
SYNC_ERROR_MAX_LENGTH = 2000

_revocation_cause = contextvars.ContextVar("badge_revocation_cause", default=None)
_owns_recalculation = contextvars.ContextVar("badge_owns_recalculation", default=False)


@contextmanager
def revocation_cause(description):
    """Name what is about to change achievement counts, for the audit trail.

    A cascade revocation records only arithmetic, which tells support that a count
    fell but not what moved it. Anything changing grants in bulk should wrap the
    work in this so the note says which operation was responsible.
    """
    token = _revocation_cause.set(description)
    try:
        yield
    finally:
        _revocation_cause.reset(token)


@contextmanager
def owns_recalculation():
    """Take over recalculating from the ``post_delete`` signal for this block.

    The signal fires per row, and a member's badges are derived from a count
    rather than adjusted by a delta, so deleting ten of one member's grants
    recalculates the same answer ten times. A bulk delete that knows which members
    it touched can do it once each instead, which is what this suspends the signal
    for.

    Only the delete side needs it. Grants are inserted with ``bulk_create``, which
    does not send ``post_save`` at all.

    The contract is the name: inside this block, deleting a grant no longer keeps
    the member's badges honest, so the block itself has to. Not a way to make a
    delete cheaper, a way to move the same work somewhere it can be batched.
    """
    token = _owns_recalculation.set(True)
    try:
        yield
    finally:
        _owns_recalculation.reset(token)


def recalculation_is_owned():
    """Whether a caller has taken responsibility for recalculating, for signals."""
    return _owns_recalculation.get()


def discard_source_achievements(model, object_ids):
    """Delete automatic grants pointing at the given rows and recalculate.

    A grant reaches its source through a generic foreign key, which carries no
    referential integrity, so deleting a source row on its own leaves a grant
    still counting toward a threshold. Call this first.

    Atomic in itself, so the grants and the badges they justify move together
    whether or not the caller has a transaction of its own around the source rows.
    """
    object_ids = list(object_ids)
    if not object_ids:
        return
    content_type = ContentType.objects.get_for_model(model)
    grants = UserAchievement.objects.filter(
        source_content_type=content_type, source_object_id__in=object_ids
    )
    pairs = set(grants.values_list("user_id", "achievement_id"))
    # The pairs are known before the delete, so the per-row signal can only reach
    # the same answer once per row instead of once per pair.
    #
    # Atomic here as well as at the caller: deleting a grant without recalculating
    # it in the same transaction leaves a member holding a badge nothing supports,
    # and leaves nothing behind to notice it by. Cheap to guarantee locally rather
    # than depend on every future caller reading the paragraph above.
    with transaction.atomic():
        with owns_recalculation():
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

    ``recalculated`` is the part of ``changed`` this run has already brought up to
    date, which is every member it deleted from: those are recalculated per chunk
    so that a run dying half way leaves the badges it got to correct. A caller
    recalculating ``changed - recalculated`` does exactly the work still owing.
    Empty on a dry run, and empty for an additive run, which deletes nothing and
    whose ``bulk_create`` sends no signal.
    """

    slug: str
    yielded: int
    added: int
    removed: int
    changed: frozenset
    applied: bool
    refused: bool
    recalculated: frozenset = frozenset()
    run_id: int | None = None

    def outstanding(self):
        """The members a caller still has to recalculate after this run."""
        return self.changed - self.recalculated

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
    trigger=SyncTrigger.COMMAND,
    actor=None,
):
    """Make the stored automatic grants for one source agree with that source.

    One walk answers both halves: a pair the source yields with no row behind it is
    created, and a stored row the source never yields is stale and deleted.
    ``backfill_achievements`` is this with ``remove=False``, which is why it cannot
    undo anything and why the weekly pipeline is safe to point at it.

    Manual grants are never touched, and an *invalidated* automatic row is matched
    like any other, so an admin's judgement is never overwritten by a re-add. An
    automatic row with no source pointer counts as stale: nothing can create one and
    it can never match what an iterator yields.

    Stale grants are **deleted, not invalidated**: the uniqueness constraint on
    automatic grants ignores ``is_valid``, so a tombstone would permanently block
    the grant from being re-created if the attribution came back.

    Badges are recalculated here only for the members this run *deleted* from, once
    per member per chunk, because the chunked delete is only crash-safe if the
    badges move with it. Everything else is left to the caller, which knows whether
    it is looking at one member or the whole table and whether a dry run means there
    is nothing to do: see ``SourceSync.outstanding``.

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
        trigger: What started this run, for the sync log.
        actor: The admin who started it, where a person did.

    Returns:
        A ``SourceSync``. ``refused`` is set when the iterator yielded no pairs
        while stale grants exist, which is indistinguishable from a broken source
        and would otherwise revoke every badge the source feeds. Nothing is
        deleted in that case unless ``allow_empty`` says so; the additive half is
        unaffected, there being nothing to add.

    Raises:
        Whatever the source iterator or the writes raise, after naming it on the
        run so a half-finished reconcile is not left looking like one still in
        progress.
    """
    run = None
    if not dry_run:
        run = AchievementSyncRun.objects.create(
            source_slug=slug,
            mode=SyncMode.RECONCILE if remove else SyncMode.BACKFILL,
            trigger=trigger,
            triggered_by=actor,
        )
    # Named on every badge this run revokes, so support can follow a vanished badge
    # back to the operation that moved the count.
    with revocation_cause(None if run is None else str(run)):
        try:
            return _sync_source(
                slug,
                achievement,
                run=run,
                user_ids=user_ids,
                add=add,
                remove=remove,
                dry_run=dry_run,
                allow_empty=allow_empty,
                batch_size=batch_size,
            )
        except Exception as exc:
            # An unfinished row is otherwise indistinguishable from a run still in
            # flight, and the deletes are chunked rather than transactional, so a
            # half-done reconcile has already revoked badges that this row is the
            # only record of. Re-raised: the command still exits non-zero and the
            # task still fails.
            _fail_run(run, exc)
            raise


def _fail_run(run, exc):
    """Record that a run died, without letting the bookkeeping hide why.

    ``finished_at`` is stamped as well as ``error``: the run stopped, and leaving it
    open would keep reading as in flight. Best effort - a failure here must never
    replace the exception on its way out, so a connection left unusable by the
    original error costs a log line and nothing else.
    """
    if run is None:
        return
    run.error = f"{type(exc).__name__}: {exc}"[:SYNC_ERROR_MAX_LENGTH]
    run.finished_at = timezone.now()
    try:
        run.save(update_fields=["error", "finished_at"])
    except DatabaseError:
        logger.exception("Could not record the failure of %s", run)


def _finish_run(run, result):
    """Record what a run did and hand the result back with its id attached."""
    if run is None:
        return result
    run.added = result.added
    run.removed = 0 if result.refused else result.removed
    run.members_changed = len(result.changed)
    run.refused = result.refused
    run.finished_at = timezone.now()
    run.save(
        update_fields=[
            "added",
            "removed",
            "members_changed",
            "refused",
            "finished_at",
        ]
    )
    return result._replace(run_id=run.pk)


def _sync_source(
    slug,
    achievement,
    *,
    run,
    user_ids,
    add,
    remove,
    dry_run,
    allow_empty,
    batch_size,
):
    """The walk itself. See ``sync_source``, which owns the run log around it."""
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

    # Paired with the member each row belongs to, so a chunk can recalculate the
    # members it just emptied without going back to the database to ask who they
    # were.
    stale = (
        [(pk, user_id) for (user_id, _, _), pks in unmatched.items() for pk in pks]
        if remove
        else []
    )
    if stale and not yielded and not allow_empty:
        logger.warning(
            "Refusing to remove %s stale grant(s) for '%s': the source yielded "
            "nothing at all. Pass allow_empty to override.",
            len(stale),
            slug,
        )
        return _finish_run(
            run,
            SourceSync(
                slug, yielded, added, len(stale), frozenset(changed), not dry_run, True
            ),
        )

    if remove:
        changed.update(user_id for user_id, _, _ in unmatched)

    recalculated = set()
    if stale and not dry_run:
        # One transaction per chunk, and never one for the whole run: a run that
        # dies half way is then simply a run to repeat, because every chunk either
        # happened with its recalculations or did not happen at all.
        #
        # The pairing is what makes that true, and it is not optional. Deleting a
        # grant outside the same transaction that recalculates it leaves a member
        # holding a badge their count no longer supports, *and* leaves no trace of
        # it: a second reconcile finds their grants already gone, so it reports
        # nothing changed and recalculates nobody. Only a full recalculation would
        # find them.
        for start in range(0, len(stale), batch_size):
            chunk = stale[start : start + batch_size]
            members = {user_id for _, user_id in chunk}
            with transaction.atomic():
                with owns_recalculation():
                    UserAchievement.objects.filter(
                        pk__in=[pk for pk, _ in chunk]
                    ).delete()
                for user_id in members:
                    recalculate_badges(user_id, achievement.pk)
            recalculated.update(members)

    return _finish_run(
        run,
        SourceSync(
            slug,
            yielded,
            added,
            len(stale),
            frozenset(changed),
            not dry_run,
            False,
            recalculated=frozenset(recalculated),
        ),
    )


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
