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
from badges.models import Achievement, UserBadge
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
    """The badge the member picked, else the highest one they hold, else ``None``.

    A pick always wins, a lower rung included: which badge leads is the point of
    the picker. Any pick that does not resolve - unset, revoked, or folded away
    by ``held_badges`` - falls back to the top rank held.

    The fallback reverses the earlier rule, which featured nothing without a
    deliberate save (issue #2702). Almost nobody makes that save, so a member
    with a full card of badges showed none beside their name. ``hide_badges``
    still wins, the fallback reaching only what ``held_badges`` allows.

    ``display_badge_id`` is read rather than ``display_badge`` because a page
    rendering many users would otherwise cost a query each: the picked row, when
    the member still holds it, is already among ``held_badges``.
    """
    held = held_badges(user, include_hidden=include_hidden)
    picked = user.display_badge_id
    if picked is not None:
        for row in held:
            if row.pk == picked:
                return badge_card(row)
    return badge_card(held[0]) if held else None


def badge_cards(user, include_hidden=False):
    """Each badge category as one card, its highest rank, highest rank first.

    Climbing keeps the rungs below, so bronze-to-gold in one category listed the
    same badge three times - eleven rows for six badges in issue #2702. Only the
    rung reached is a badge to show.

    Deduped here rather than in ``held_badges``, which is what ``featured_badge``
    validates a pick against: a member may feature a lower rung, and folding it
    away there would silently override them.
    """
    unique = {}
    for badge in held_badges(user, include_hidden=include_hidden):
        unique.setdefault(badge.badge_id, badge)
    return [badge_card(badge) for badge in unique.values()]


def achievement_cards(user):
    """The member's earned achievements, as the dicts the achievement card reads.

    Only achievements with a valid grant: the card records what the member did,
    so a zero is not a row. Deduped by achievement, ``user_badge_summary``
    emitting a row per achievement/badge pair while an achievement feeding two
    badges is still one tally.

    Highest tally first, name breaking ties - the registry orders by name alone,
    which buries the tallies the card is built around.
    """
    cards = {}
    for row in user_badge_summary(user):
        if row.valid_grants:
            cards[row.achievement.pk] = {
                "title": row.achievement.name,
                "points": row.valid_grants,
                "description": row.achievement.description,
            }
    return sorted(cards.values(), key=lambda card: (-card["points"], card["title"]))


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


# The recognition dialogs explain the whole scheme rather than one member's
# standing, so their rows take no user.
#
# The Achievements dialog names each achievement type, which is catalogue data.
# The Badges dialog names the two kinds of badge instead, and neither is a
# ``Badge`` row: one stands for the whole catalogue, the other for tenure stars,
# which are not badges.
#
# Boost Day is design-owned for a different reason: it and the tenure stars are
# applied automatically from a date rather than accumulated from grants, so they
# are display states rather than earned records and no ``Achievement`` exists.
BOOST_DAY_ROW = {
    "token": BadgeToken.BOOST_DAY,
    "name": "Boost day celebration",
    "description": (
        "A celebration of the day you joined Boost. Awarded annually to mark "
        "another year as part of the community."
    ),
}

ACHIEVEMENT_BASED_ROW = {
    "token": BadgeToken.ACHIEVEMENT_BASED,
    "size": "large",
    "name": "Achievement-based",
    "description": (
        "Reflects the depth of your contributions. Accumulate achievements to "
        "unlock five tiers; Bronze, Silver, Gold, Platinum and Diamond."
    ),
}

TENURE_ROW = {
    "token": BadgeToken.TENURE_BASED,
    "size": "large",
    "name": "Tenure-based",
    "description": (
        "Awarded in recognition of your time on the platform. The longer you've "
        "been part of the Boost community, the higher the tier you unlock."
    ),
}

ACHIEVEMENTS_DIALOG_DESCRIPTION = (
    "Achievements capture your contributions to Boost — automatically tracked "
    "where possible, manually verified for high-value activities."
)

BADGES_DIALOG_DESCRIPTION = (
    "Badges recognize your journey on Boost — from the contributions you make "
    "to the time you've invested and the milestones you've reached along the way."
)


PLACEHOLDER_ACHIEVEMENT_COUNT = 1


def achievement_dialog_rows(user=None):
    """Every achievement type as a dialog row, Boost Day last.

    Each row carries a counter, which is what the design asks for: the tally is
    the point, the artwork being the same for every achievement type.

    Given a member, the counters are that member's own valid grants.

    Nothing earned shows the placeholder rather than a zero, whether or not
    there is a member to count: the dialog explains how achievements work, and
    the counter is artwork carrying an example figure. A wall of ``00`` reads as
    a broken counter instead.

    Ordered by name, ``Achievement`` being an admin-editable registry with no
    catalogue ordering of its own.
    """
    counts = {} if user is None else _valid_grant_counts(user)
    rows = [
        {
            "token": BadgeToken.ACHIEVEMENT_COUNT,
            "count": counts.get(achievement.pk) or PLACEHOLDER_ACHIEVEMENT_COUNT,
            "name": achievement.name,
            "description": achievement.description,
        }
        for achievement in Achievement.objects.all()
    ]
    return rows + [BOOST_DAY_ROW]


def _valid_grant_counts(user):
    """How many valid grants the member holds of each achievement, by pk.

    Read through ``user_badge_summary`` so "a valid grant" keeps one definition
    across the app. It counts ``is_valid`` rows and leaves invalidated ones out.
    """
    return {row.achievement.pk: row.valid_grants for row in user_badge_summary(user)}


def badge_dialog_rows():
    """The two kinds of badge, as dialog rows.

    Fixed copy rather than catalogue rows: "Achievement-based" covers the whole
    catalogue at once, and tenure stars are not badges at all.
    """
    return [ACHIEVEMENT_BASED_ROW, TENURE_ROW]
