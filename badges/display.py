"""Rows for the user-profile-edit display-badge picker.

Per-tier copy is a map keyed by ``BadgeLabel``: a fixed enum, and design-owned
wording rather than something staff tune beside a threshold.

Every row is built from ``badges.summary.user_badge_summary``, so the picker adds
no queries of its own.
"""

from typing import NamedTuple

from badges.enums import BadgeLabel, TierRank, label_order, rank_order
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

    ``earned`` takes ``count`` (what the member has done) and ``unit``; ``locked``
    takes the tier's threshold in those slots; ``verb`` is the imperative the held
    row's "N more ..." clause is built from.
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
    earned = phrases.earned.format(count=count, unit=_unit(phrases, count))
    if is_held and gap:
        return (
            f"{earned}, {phrases.verb} {gap} more {_unit(phrases, gap)} "
            "to unlock the next badge"
        )
    return earned


def _unit(phrases, count):
    """The badge's unit noun, pluralised for ``count``."""
    return phrases.unit if count == 1 else phrases.plural
