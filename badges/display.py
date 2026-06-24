"""Turning a user's awarded badges into what the v3 badge templates render.

Those templates take a component token and a label, never a model instance, so
the rank-to-asset mapping belongs here rather than on the user model.

Ordering is by *rank*, not threshold: thresholds are not comparable across
badges (a reviewer diamond needs 5 achievements, a commits silver needs 12), so
the raw threshold only breaks ties within a rank.
"""

from django.db.models import Prefetch
from django.utils import timezone

from badges.enums import TierRank, rank_order
from badges.models import UserBadge
from core.constants import BadgeToken

TIER_TOKENS = {
    TierRank.BRONZE: BadgeToken.TIER_1,
    TierRank.SILVER: BadgeToken.TIER_2,
    TierRank.GOLD: BadgeToken.TIER_3,
    TierRank.PLATINUM: BadgeToken.TIER_4,
    TierRank.DIAMOND: BadgeToken.TIER_5,
}


def active_badges_prefetch(lookup="badges"):
    """The rows ``held_badges`` reads, prefetched at ``lookup``.

    Callers rendering many users at once (author cards on a news page) need this,
    or ``held_badges`` queries once per user instead of reading the cache.

    ``lookup`` exists because the path is load-bearing. A queryset that reaches
    its users through ``select_related`` cannot be handed
    ``Prefetch("author", queryset=User.objects.prefetch_related(...))``: Django
    finds the foreign key already cached, skips the prefetch, and silently drops
    the nested badge prefetch with it. Such a caller asks for the badges through
    the path instead - ``active_badges_prefetch("author__badges")``.
    """
    return Prefetch(
        lookup,
        queryset=UserBadge.objects.active().select_related("badge", "tier"),
    )


def held_badges(user, include_hidden=False):
    """The user's active badges, highest rank first, each rank once.

    Returns an empty list when the user has hidden their badges, unless
    ``include_hidden`` is set - which only the owner's own views should do.

    Retiring a tier keeps the badges already awarded against it, so a user who
    also qualifies under its replacement holds the same rank twice. Both rows are
    real history; only one of them is a badge to show.
    """
    if user.hide_badges and not include_hidden:
        return []
    if "badges" in getattr(user, "_prefetched_objects_cache", {}):
        rows = [badge for badge in user.badges.all() if badge.revoked_at is None]
    else:
        rows = list(user.badges.active().select_related("badge", "tier"))

    unique = {}
    for row in sorted(rows, key=_rank_key, reverse=True):
        unique.setdefault((row.badge_id, row.tier.rank), row)
    return list(unique.values())


def featured_badge(user, include_hidden=False):
    """The user's headline badge as a card dict, or ``None`` if they hold none.

    Display-only for now; letting the user choose which badge to feature comes
    later.
    """
    badges = held_badges(user, include_hidden=include_hidden)
    return badge_card(badges[0]) if badges else None


def badge_cards(user, include_hidden=False):
    """Every active badge as a card dict, highest rank first."""
    return [
        badge_card(badge) for badge in held_badges(user, include_hidden=include_hidden)
    ]


def badge_card(user_badge):
    """One awarded badge as the dict the badge templates read.

    ``awarded_at`` is stored in UTC, so the calendar day has to be taken in the
    project's timezone rather than off the raw value: an evening award would
    otherwise be dated to the following day everywhere west of UTC.
    """
    return {
        "name": user_badge.badge.get_label_display(),
        "icon": TIER_TOKENS[user_badge.tier.rank],
        "earned_date": timezone.localtime(user_badge.awarded_at).date(),
    }


def _rank_key(user_badge):
    """Sort key placing the highest rank first, threshold breaking ties."""
    return rank_order(user_badge.tier.rank), user_badge.tier.threshold
