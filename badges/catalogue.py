"""Canonical achievement / badge / tier catalogue.

Values come from the Boost achievement-to-badge mapping spreadsheet. A bootstrap
fixture, not a live source of truth: a tier is created only when its badge has no
row for that rank at all, so re-seeding cannot undo a threshold staff have tuned
or resurrect a rank they retired. (Not "no *active* row": a retuned rank has both
a retired row and its replacement, and matching on rank finds both.)

Editing a threshold here therefore only affects databases that were never seeded.
To change one everywhere, edit it here *and* add a data migration that retires
the existing rows and creates replacements - updating in place would revoke every
member who only met the old number.

``seed_catalogue`` takes model classes as arguments so a data migration can pass
historical models while tests pass the real ones.
"""

from badges.enums import AchievementSlug, BadgeLabel, TierRank

# (slug, name, description, badge_label, {rank: threshold})
CATALOGUE = [
    (
        AchievementSlug.LIBRARY_AUTHORING,
        "Library Authoring",
        "Authored an original Boost library accepted into the collection.",
        BadgeLabel.LIBRARY_AUTHOR,
        {
            TierRank.BRONZE: 1,
            TierRank.SILVER: 2,
            TierRank.GOLD: 4,
            TierRank.PLATINUM: 7,
            TierRank.DIAMOND: 14,
        },
    ),
    (
        AchievementSlug.LIBRARY_VERSIONING,
        "Library Versioning",
        "Authored new versions / releases of Boost libraries.",
        BadgeLabel.VERSION_AUTHOR,
        {
            TierRank.BRONZE: 10,
            TierRank.SILVER: 27,
            TierRank.GOLD: 73,
            TierRank.PLATINUM: 197,
            TierRank.DIAMOND: 533,
        },
    ),
    (
        AchievementSlug.CODE_COMMITS,
        "Code Commits",
        "Commits authored to any Boost repository.",
        BadgeLabel.COMMITS_MASTER,
        {
            TierRank.BRONZE: 1,
            TierRank.SILVER: 12,
            TierRank.GOLD: 138,
            TierRank.PLATINUM: 1613,
            TierRank.DIAMOND: 18920,
        },
    ),
    (
        AchievementSlug.LIBRARY_REVIEW,
        "Library Review",
        "Formal review submissions on Boost proposals.",
        BadgeLabel.REVIEWER,
        {
            TierRank.BRONZE: 1,
            TierRank.SILVER: 2,
            TierRank.GOLD: 3,
            TierRank.PLATINUM: 4,
            TierRank.DIAMOND: 5,
        },
    ),
    (
        AchievementSlug.LIBRARY_MAINTENANCE,
        "Library Maintenance",
        "Number of libraries actively maintained.",
        BadgeLabel.MAINTAINER,
        {
            TierRank.BRONZE: 1,
            TierRank.SILVER: 2,
            TierRank.GOLD: 5,
            TierRank.PLATINUM: 10,
            TierRank.DIAMOND: 20,
        },
    ),
    (
        AchievementSlug.DOCUMENTATION,
        "Documentation",
        "Doc contributions using standardised Boost tooling (Antora / BoostLook).",
        BadgeLabel.DOCUMENTER,
        {
            TierRank.BRONZE: 1,
            TierRank.SILVER: 3,
            TierRank.GOLD: 7,
            TierRank.PLATINUM: 19,
            TierRank.DIAMOND: 50,
        },
    ),
    (
        AchievementSlug.MAILING_LIST,
        "Mailing List Participation",
        "Participation on the Boost developers mailing list.",
        BadgeLabel.REGULAR,
        {
            TierRank.BRONZE: 1,
            TierRank.SILVER: 3,
            TierRank.GOLD: 6,
            TierRank.PLATINUM: 15,
            TierRank.DIAMOND: 37,
        },
    ),
    (
        AchievementSlug.PUBLISHER,
        "News Posts Published",
        "Articles / news posts published on Boost.org.",
        BadgeLabel.PUBLISHER,
        {
            TierRank.BRONZE: 1,
            TierRank.SILVER: 3,
            TierRank.GOLD: 7,
            TierRank.PLATINUM: 19,
            TierRank.DIAMOND: 50,
        },
    ),
]


def seed_catalogue(achievement_model, badge_model, badge_tier_model):
    """Idempotently create the catalogue using the given model classes."""
    for slug, name, description, label, tiers in CATALOGUE:
        achievement, _created = achievement_model.objects.get_or_create(
            slug=slug, defaults={"name": name, "description": description}
        )
        badge, _created = badge_model.objects.get_or_create(
            label=label,
            defaults={"achievement": achievement, "description": description},
        )
        for rank, threshold in tiers.items():
            # Not get_or_create: a retuned rank has both a retired row and its
            # replacement, and get() over the pair raises MultipleObjectsReturned.
            if not badge_tier_model.objects.filter(badge=badge, rank=rank).exists():
                badge_tier_model.objects.create(
                    badge=badge, rank=rank, threshold=threshold
                )
