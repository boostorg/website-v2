"""Rows for the user-profile-edit display-badge picker.

Per-tier copy is a map keyed by ``BadgeLabel``: a fixed enum, and design-owned
wording rather than something staff tune beside a threshold.

Every row is built from ``badges.summary.user_badge_summary``, so the picker adds
no queries of its own.

The same module turns a user's awarded badges into what the v3 badge templates
render. Those templates take a component token and a label, never a model
instance, so the rank-to-asset mapping belongs here rather than on the user
model.

Ordering there is by *rank*, not threshold: thresholds are not comparable across
badges (a reviewer diamond needs 5 achievements, a commits silver needs 12), so
the raw threshold only breaks ties within a rank.
"""

from typing import NamedTuple

from django.db.models import Prefetch
from django.utils import timezone

from badges.enums import BadgeLabel, TierRank, label_order, rank_order
from badges.models import UserBadge
from badges.summary import user_badge_summary
from core.constants import BadgeToken

TIER_TOKENS = {
    TierRank.BRONZE: BadgeToken.TIER_1,
    TierRank.SILVER: BadgeToken.TIER_2,
    TierRank.GOLD: BadgeToken.TIER_3,
    TierRank.PLATINUM: BadgeToken.TIER_4,
    TierRank.DIAMOND: BadgeToken.TIER_5,
}


class BadgePhrases(NamedTuple):
    """How one badge describes a tier, earned and not yet earned.

    ``earned`` and ``locked`` take ``count`` (the tier's threshold) and ``unit``;
    ``verb`` is the imperative the held row's "N more ..." clause is built from.
    """

    earned: str
    locked: str
    unit: str
    plural: str
    verb: str


PHRASES = {
    BadgeLabel.LIBRARY_AUTHOR: BadgePhrases(
        "Authored {count} {unit}",
        "Author {count} {unit} to unlock",
        "library",
        "libraries",
        "author",
    ),
    BadgeLabel.VERSION_AUTHOR: BadgePhrases(
        "Authored {count} {unit} of Boost libraries",
        "Author {count} {unit} of Boost libraries to unlock",
        "release",
        "releases",
        "author",
    ),
    BadgeLabel.COMMITS_MASTER: BadgePhrases(
        "Authored {count} {unit}",
        "Author {count} {unit} to any Boost repository to unlock",
        "commit",
        "commits",
        "author",
    ),
    BadgeLabel.REVIEWER: BadgePhrases(
        "Submitted {count} formal {unit}",
        "Submit {count} formal {unit} on Boost proposals to unlock",
        "review",
        "reviews",
        "submit",
    ),
    BadgeLabel.MAINTAINER: BadgePhrases(
        "Maintaining {count} {unit}",
        "Maintain {count} {unit} to unlock",
        "library",
        "libraries",
        "maintain",
    ),
    BadgeLabel.DOCUMENTER: BadgePhrases(
        "Made {count} documentation {unit}",
        "Make {count} documentation {unit} to unlock",
        "contribution",
        "contributions",
        "make",
    ),
    BadgeLabel.REGULAR: BadgePhrases(
        "Posted {count} {unit} on the developers mailing list",
        "Post {count} {unit} on the Boost developers mailing list to unlock",
        "time",
        "times",
        "post",
    ),
    BadgeLabel.PUBLISHER: BadgePhrases(
        "Published {count} {unit} on Boost.org",
        "Publish {count} {unit} on Boost.org to unlock",
        "article",
        "articles",
        "publish",
    ),
}

# So a BadgeLabel added without a phrase renders instead of raising.
GENERIC_PHRASES = BadgePhrases(
    "{count} {unit} earned",
    "Earn {count} {unit} to unlock",
    "achievement",
    "achievements",
    "earn",
)


class _BadgeGroup(NamedTuple):
    """One badge's rows, with the keys the picker is ordered by."""

    label: str
    earned_rank: int | None
    options: list


def badge_options(user):
    """One row per badge category, unlocked ones first.

    A badge under way shows the rung held, whose copy states how much more the
    next one takes; a badge not started shows its first tier. Unlocked badges
    lead, highest rank first, then locked ones in catalogue order.

    A row is selectable only where the member holds an active ``UserBadge``, that
    being the only thing there is to store: a manually revoked rung has its
    threshold met but can never be picked, recalculation not undoing one.
    """
    groups = [
        _badge_group(row) for row in user_badge_summary(user) if row.badge is not None
    ]
    groups = [group for group in groups if group.options]
    unlocked = [group for group in groups if group.earned_rank is not None]
    locked = [group for group in groups if group.earned_rank is None]
    # Highest rank first, catalogue order breaking ties.
    unlocked.sort(key=lambda group: (-group.earned_rank, label_order(group.label)))
    locked.sort(key=lambda group: label_order(group.label))
    return [option for group in unlocked + locked for option in group.options]


def default_option(options):
    """The row the picker opens on when the member has chosen none.

    The first selectable row, ``badge_options`` already returning them highest
    rank first with catalogue order breaking ties. ``None`` when nothing is held.
    """
    return next((row["value"] for row in options if row["selectable"]), None)


def resolve_selection(options, selected):
    """``selected`` if the picker still offers it, otherwise the default row.

    A stored choice can stop being offered without being revoked: a badge shows
    only the rung its holder has reached, so climbing from bronze to silver
    retires the bronze row while the bronze ``UserBadge`` stays active. Seeding
    a value with no row leaves the trigger blank, so fall back to the default.
    """
    offered = {row["value"] for row in options if row["selectable"]}
    return selected if selected in offered else default_option(options)


def _badge_group(summary_row):
    """Build one badge's row and the keys its group is ordered by.

    One row per badge. For a badge under way that is the rung held, whose copy
    carries the distance to the next; for one not started, the bottom rung.
    ``summary_row.held`` is the rung reached, ranked the way the ladder is - and
    it may sit on a retired tier, retirement keeping the badges awarded under it.
    """
    badge = summary_row.badge
    user_badge = summary_row.held
    if user_badge is not None:
        tier = user_badge.tier
    elif badge.active_tiers:
        tier = badge.active_tiers[0]
    else:
        # Nothing held and nothing awardable: no row rather than an unreachable one.
        return _BadgeGroup(label=badge.label, earned_rank=None, options=[])

    phrases = PHRASES.get(badge.label, GENERIC_PHRASES)
    option = {
        "value": "" if user_badge is None else user_badge.pk,
        "name": badge.get_label_display(),
        "detail": _detail(
            phrases,
            tier,
            summary_row.valid_grants,
            user_badge is not None,
            summary_row.gap,
        ),
        "icon": TIER_TOKENS[tier.rank],
        "rank": tier.get_rank_display(),
        "selectable": user_badge is not None,
    }
    return _BadgeGroup(
        label=badge.label,
        earned_rank=rank_order(tier.rank) if user_badge is not None else None,
        options=[option],
    )


def _detail(phrases, tier, count, is_held, gap):
    """The row's second column: what was done, or what the rung takes.

    The rung held also carries the distance to the next one, there being no row
    of its own for it. No gap means no rung above this one.
    """
    if count < tier.threshold:
        return phrases.locked.format(
            count=tier.threshold, unit=_unit(phrases, tier.threshold)
        )
    earned = phrases.earned.format(
        count=tier.threshold, unit=_unit(phrases, tier.threshold)
    )
    if is_held and gap:
        return (
            f"{earned}, {phrases.verb} {gap} more {_unit(phrases, gap)} "
            "to unlock the next badge"
        )
    return earned


def _unit(phrases, count):
    """The badge's unit noun, pluralised for ``count``."""
    return phrases.unit if count == 1 else phrases.plural


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
