"""Why one member does or does not show a badge.

An admin diagnostic, deliberately separate from ``badges.display``: that module
is the public-profile rendering layer and answers "what do we show", while this
one answers "why", including for the badges a member does *not* have. The four
causes of a missing badge - below threshold, cascade-revoked, manually revoked,
hidden by the member - live in three different changelists otherwise, and two of
them are only visible as arithmetic against a threshold.

Everything is read in a fixed number of queries, so the cost does not grow with
the number of achievement types an admin has created.
"""

from dataclasses import dataclass

from django.db.models import Count, Prefetch, Q

from badges.enums import rank_order
from badges.models import (
    RANK_LADDER_ORDER,
    Achievement,
    Badge,
    BadgeTier,
    RevocationSource,
    UserAchievement,
    UserBadge,
)


@dataclass(frozen=True)
class AchievementRow:
    """One achievement, one badge it feeds, and the member's state against it."""

    achievement: Achievement
    badge: Badge | None
    valid_grants: int
    invalid_grants: int
    held: UserBadge | None
    next_tier: BadgeTier | None
    revoked: list[UserBadge]
    reason: str

    @property
    def gap(self):
        """Valid grants still needed to reach ``next_tier``, if there is one."""
        if self.next_tier is None:
            return None
        return max(self.next_tier.threshold - self.valid_grants, 0)


def user_badge_summary(user):
    """One row per achievement type and badge, with why the member shows it.

    An achievement that feeds no badge still gets a row: its grants accumulate
    and can never become anything, which is worth seeing. An achievement that
    feeds several gets one row each, because each badge has its own ladder and
    its own answer.
    """
    counts = {
        row["achievement_id"]: row
        for row in UserAchievement.objects.filter(user=user)
        .values("achievement_id")
        .annotate(
            valid=Count("pk", filter=Q(is_valid=True)),
            invalid=Count("pk", filter=Q(is_valid=False)),
        )
    }
    achievements = Achievement.objects.prefetch_related(
        Prefetch(
            "badges",
            queryset=Badge.objects.prefetch_related(
                Prefetch(
                    "tiers",
                    # Up the ladder, which is the order the page presents them in.
                    queryset=BadgeTier.objects.filter(is_active=True).order_by(
                        RANK_LADDER_ORDER
                    ),
                    to_attr="active_tiers",
                )
            ),
        )
    )
    awarded = {}
    # ``revoked_by`` is joined because a manual revocation names the admin who
    # made it, which would otherwise be a query per revoked badge.
    for user_badge in UserBadge.objects.filter(user=user).select_related(
        "badge", "tier", "revoked_by"
    ):
        awarded.setdefault(user_badge.badge_id, []).append(user_badge)

    rows = []
    for achievement in achievements:
        grants = counts.get(achievement.pk, {})
        valid = grants.get("valid", 0)
        invalid = grants.get("invalid", 0)
        badges = list(achievement.badges.all())
        if not badges:
            rows.append(_row(user, achievement, None, valid, invalid, []))
            continue
        for badge in badges:
            rows.append(
                _row(
                    user,
                    achievement,
                    badge,
                    valid,
                    invalid,
                    awarded.get(badge.pk, []),
                )
            )
    return rows


def _row(user, achievement, badge, valid, invalid, user_badges):
    """Assemble one row from the member's badge rows for a single badge."""
    held = _highest_held(user_badges)
    revoked = sorted(
        (row for row in user_badges if row.revoked_at is not None),
        key=lambda row: row.revoked_at,
        reverse=True,
    )
    next_tier = _next_tier(badge, held, user_badges)
    return AchievementRow(
        achievement=achievement,
        badge=badge,
        valid_grants=valid,
        invalid_grants=invalid,
        held=held,
        next_tier=next_tier,
        revoked=revoked,
        reason=_reason(user, badge, valid, held, next_tier, revoked),
    )


def _highest_held(user_badges):
    """The best tier the member currently holds for one badge.

    Ranked by ``TierRank`` order, not by threshold. Retiring a tier keeps the
    badges awarded against it, so a badge can hold a retired gold at 3 next to a
    live bronze at 6 and the higher threshold is then the *lower* rank.
    Threshold only breaks ties between two rows of the same rank.
    """
    active = [row for row in user_badges if row.revoked_at is None]
    if not active:
        return None
    return max(active, key=lambda row: (rank_order(row.tier.rank), row.tier.threshold))


def _next_tier(badge, held, user_badges):
    """The lowest rung the member can still climb to, by rank.

    Keyed on the member's *rank*, not on their grant count. Counting from the
    count picks the tier with the lowest unmet threshold, which after a retuning
    is a rank the member has already passed: shift a whole ladder up by five and
    a gold holder's "next" rank becomes bronze, which is not a rung anyone climbs
    to from gold. Their next rung is platinum, and the threshold is then the
    answer to "how many do I need", not the question.

    Ranks with no active tier are skipped rather than reported as unreachable, so
    a badge whose silver has been retired sends a bronze holder to gold.

    A manually revoked rank is skipped too, because recalculation will not give it
    back however many grants arrive - ``services._award_tier`` refuses to - so it
    is not the rung anyone is waiting for. A cascade revocation is left in place:
    that one does come back on its own once the count recovers.
    """
    if badge is None:
        return None
    floor = -1 if held is None else rank_order(held.tier.rank)
    blocked = {
        row.tier_id
        for row in user_badges
        if row.revoked_at is not None
        and row.revocation_source == RevocationSource.MANUAL
    }
    above = [
        tier
        for tier in badge.active_tiers
        if rank_order(tier.rank) > floor and tier.pk not in blocked
    ]
    return min(above, key=lambda tier: rank_order(tier.rank), default=None)


def _reason(user, badge, valid, held, next_tier, revoked):
    """Plain English for the state the row is in.

    Ordered by what a support request is actually asking. A configuration fault
    outranks anything about the member, because no answer about the member is
    meaningful while the badge cannot award at all.
    """
    if badge is None:
        return "No badge is configured for this achievement."
    if not badge.active_tiers:
        return "The badge has no active tiers, so it awards nothing."
    if held is not None:
        return _held_reason(user, held, valid)
    if revoked:
        return _revoked_reason(revoked, valid)
    # Past the two branches above the member has no badge rows at all for this
    # badge, so nothing is blocking the bottom of the ladder and ``next_tier`` is
    # the lowest active tier rather than None.
    if valid < next_tier.threshold:
        return (
            f"Not earned - {valid} of {next_tier.threshold} for "
            f"{next_tier.get_rank_display()}."
        )
    # The threshold for the next rung is already met and no badge row exists, so
    # recalculation has not run since the grants arrived. Only reachable if
    # something wrote grants without firing the signals - a bulk insert, raw
    # SQL, a restored dump. Naming the highest rung the count reaches says what
    # recalculating would actually hand out, which the next rung alone does not.
    reached = max(
        (tier for tier in badge.active_tiers if valid >= tier.threshold),
        key=lambda tier: rank_order(tier.rank),
    )
    return (
        f"Not earned, but {valid} valid grants already reaches "
        f"{reached.get_rank_display()}. Recalculate to award it."
    )


def _held_reason(user, held, valid):
    """Why a held badge does or does not reach the member's profile.

    The stale case comes first: ``hide_badges`` is stated once at the top of the
    page already, whereas a badge held below its own threshold is an
    inconsistency nothing else on the page names.
    """
    rank = held.tier.get_rank_display()
    since = held.awarded_at.date()
    if valid < held.tier.threshold:
        return (
            f"Held since {since} ({rank}), but only {valid} valid grants against "
            f"a threshold of {held.tier.threshold}. Recalculate to reconcile."
        )
    if user.hide_badges:
        return "Held, but hidden - the member has turned badge display off."
    return f"Held since {since} ({rank})."


def _revoked_reason(revoked, valid):
    """Describe the revocation that is actually keeping the badge away.

    A manual revocation survives recalculation and a cascade revocation does
    not, so a manual one is the blocker whenever both are present. Within either
    group the lowest threshold is the one nearest to coming back.
    """
    manual = [
        row for row in revoked if row.revocation_source == RevocationSource.MANUAL
    ]
    row = min(manual or revoked, key=lambda candidate: candidate.tier.threshold)
    if row.revocation_source == RevocationSource.MANUAL:
        who = row.revoked_by or "an admin whose account is gone"
        note = row.revocation_notes or "no note recorded"
        return f"Revoked by {who} on {row.revoked_at.date()}: {note}"
    return f"Revoked automatically - {valid} valid grants, needs {row.tier.threshold}."
