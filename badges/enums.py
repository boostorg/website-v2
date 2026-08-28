"""Enums for achievements and badges.

``AchievementSlug`` is deliberately not a field constraint: ``Achievement`` is an
admin-editable registry and manual-only types can be added without a deploy, so
the enum names only the slugs code refers to.

``TierRank`` is ordered by declaration, bronze lowest. **That order is the primary
ordering of the ladder**; thresholds are only the arithmetic behind one rung. They
are not comparable across badges, nor reliably within one, since a retuned badge
can hold a retired bronze at 1 beside a live bronze at 6. Anything asking "which
rung is this, and which comes next" goes through ``rank_order``.
"""

from enum import StrEnum

from django.db import models
from django.utils.translation import gettext_lazy as _


class AchievementSlug(StrEnum):
    """Slugs of the achievement types the codebase refers to by name.

    Every member must be seeded on a fresh database; a test enforces that.
    Achievements created by an admin outside this enum are supported and simply
    have no code referring to them.
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
    """The fixed set of badge categories, in the order they are presented.

    Declaration order is important: ``label_order`` below reads
    it to sort the locked badges in the display-badge picker, so reordering these
    members reorders that dropdown.

    A new category needs a matching ``Badge`` row and tiers, so adding a member
    here is only the first half of the change.
    """

    LIBRARY_AUTHOR = "library_author", _("Library Author")
    VERSION_AUTHOR = "version_author", _("Version Author")
    COMMITS_MASTER = "commits_master", _("Commits Master")
    REVIEWER = "reviewer", _("Reviewer")
    MAINTAINER = "maintainer", _("Maintainer")
    DOCUMENTER = "documenter", _("Documenter")
    REGULAR = "regular", _("Regular")
    PUBLISHER = "publisher", _("Publisher")


LABEL_ORDER = {label: index for index, label in enumerate(BadgeLabel)}


def label_order(label):
    """Catalogue position of a badge label; unknown labels sort last."""
    return LABEL_ORDER.get(label, len(LABEL_ORDER))


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
