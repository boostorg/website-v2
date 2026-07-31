"""Enums for the achievements and badges system.

``BadgeLabel`` and ``TierRank`` back model fields, so they are
``models.TextChoices`` like ``SourceType`` and ``RevocationSource``.

``AchievementSlug`` is deliberately *not* a field constraint: ``Achievement`` is
an admin-editable registry, and manual-only achievement types may be added
without a deploy. The enum names the slugs that code refers to, so that subset
stays typed even though the field stays open. It is a plain ``StrEnum`` because
it backs no field.

``TierRank`` is *ordered* by declaration: ``bronze`` is the lowest rank and
``diamond`` the highest. ``TierRank.order`` exposes that position, and
``rank_order`` reads it off a rank stored as a plain string.

That declared order is the **primary** ordering of the ladder, and thresholds
are only ever the arithmetic behind one rung of it. Thresholds are not
comparable across badges (a reviewer diamond needs 5, a commits silver needs
12), and they are not reliably comparable *within* a badge either: retuning a
threshold retires the old tier and adds a replacement, so a badge can hold a
retired bronze at 1 next to a live bronze at 6, and sorting its tiers by
threshold no longer walks bronze to diamond. Anything asking "which rung is
this, and which comes next" must go through the rank order.
"""

from enum import StrEnum

from django.db import models
from django.utils.translation import gettext_lazy as _


class AchievementSlug(StrEnum):
    """Slugs of the achievement types the codebase refers to by name.

    Every member must exist in ``badges.catalogue.CATALOGUE``; a test enforces
    that. Achievements created by an admin outside this enum are supported and
    simply have no code referring to them.
    """

    LIBRARY_AUTHORING = "library-authoring"
    LIBRARY_VERSIONING = "library-versioning"
    LIBRARY_MAINTENANCE = "library-maintenance"
    CODE_COMMITS = "code-commits"
    LIBRARY_REVIEW = "library-review"
    DOCUMENTATION = "documentation"
    MAILING_LIST = "mailing-list"
    PUBLISHER = "publisher"


class BadgeLabel(models.TextChoices):
    """The fixed set of badge categories.

    A new category needs a matching ``Badge`` row and tiers, so adding a member
    here is only the first half of the change - see ``badges.catalogue``.
    """

    LIBRARY_AUTHOR = "library_author", _("Library Author")
    VERSION_AUTHOR = "version_author", _("Version Author")
    COMMITS_MASTER = "commits_master", _("Commits Master")
    REVIEWER = "reviewer", _("Reviewer")
    MAINTAINER = "maintainer", _("Maintainer")
    DOCUMENTER = "documenter", _("Documenter")
    REGULAR = "regular", _("Regular")
    PUBLISHER = "publisher", _("Publisher")


class TierRank(models.TextChoices):
    """Ordered badge ranks, lowest to highest."""

    BRONZE = "bronze", _("Bronze")
    SILVER = "silver", _("Silver")
    GOLD = "gold", _("Gold")
    PLATINUM = "platinum", _("Platinum")
    DIAMOND = "diamond", _("Diamond")

    @property
    def order(self):
        """Zero-based position of this rank in the declared ordering."""
        return _TIER_RANK_ORDER[self]


_TIER_RANK_ORDER = {rank: index for index, rank in enumerate(TierRank)}


def rank_order(rank):
    """Ladder position of a rank held as a plain string.

    ``BadgeTier.rank`` is a ``CharField``, so callers reading one back out of the
    database have a ``str`` rather than a ``TierRank``. One function for the
    conversion keeps every "which rung is this" comparison in the codebase
    answering it the same way.
    """
    return TierRank(rank).order
