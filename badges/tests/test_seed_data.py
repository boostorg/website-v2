"""Consistency tests for the achievement / badge taxonomy.

``Achievement.slug`` is an open field by design (admins may add manual-only
types), so the slugs the codebase hard-codes are only safe if something checks
they still exist. These tests are that check: they cover the seams between
``badges.enums``, ``badges.seed_data`` and ``badges.sources``.
"""

import os
from pathlib import Path

import pytest
from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Count
from model_bakery import baker

from badges import sources
from badges.enums import AchievementSlug, BadgeLabel, TierRank
from badges.models import Achievement, Badge, BadgeTier
from badges.seed_data import SEED_CATALOGUE, seed_catalogue
from badges.services import deactivate_tier, replace_tier

SEED_SLUGS = [entry[0] for entry in SEED_CATALOGUE]
SEED_LABELS = [entry[3] for entry in SEED_CATALOGUE]

# The only places allowed to import the seed data.
SEED_DATA_IMPORTERS = ("badges/seed_data.py", "badges/migrations/", "badges/tests/")
IMPORT_FORMS = ("badges.seed_data", "from badges import seed_data")
UNSEARCHED_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", "media"}


def _project_python_files():
    """Every Python file in the tree, relative to the project root."""
    root = Path(settings.BASE_DIR)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in UNSEARCHED_DIRS]
        for name in filenames:
            if name.endswith(".py"):
                yield Path(dirpath, name).relative_to(root).as_posix()


def test_only_seeding_and_tests_import_the_seed_data():
    """Runtime code must read the taxonomy from the database, not the seed data.

    Achievements, badges and thresholds are admin-editable, so an import outside
    seeding is a second answer that stops matching the first one staff tune a
    threshold, retire a rank or add an achievement of their own.
    """
    root = Path(settings.BASE_DIR)
    offenders = [
        path
        for path in _project_python_files()
        if not path.startswith(SEED_DATA_IMPORTERS)
        and any(
            form in (root / path).read_text(errors="ignore") for form in IMPORT_FORMS
        )
    ]
    assert offenders == []


def test_every_catalogue_entry_uses_the_enums():
    """No raw strings in the catalogue: slugs, labels and ranks are all enums."""
    for slug, _name, _description, label, tiers in SEED_CATALOGUE:
        assert isinstance(slug, AchievementSlug)
        assert isinstance(label, BadgeLabel)
        for rank in tiers:
            assert isinstance(rank, TierRank)


def test_catalogue_slugs_and_labels_are_unique():
    """One achievement type per slug, one badge per label."""
    assert len(SEED_SLUGS) == len(set(SEED_SLUGS))
    assert len(SEED_LABELS) == len(set(SEED_LABELS))


def test_catalogue_covers_every_enum_member():
    """Adding an enum member without a catalogue entry is a mistake."""
    assert set(SEED_SLUGS) == set(AchievementSlug)
    assert set(SEED_LABELS) == set(BadgeLabel)


def test_every_catalogue_entry_defines_every_rank():
    """A badge with a missing rank would silently skip that tier."""
    for slug, _name, _description, _label, tiers in SEED_CATALOGUE:
        assert set(tiers) == set(TierRank), slug


def test_thresholds_increase_with_rank():
    """A lower rank must not need more achievements than a higher one."""
    for slug, _name, _description, _label, tiers in SEED_CATALOGUE:
        ordered = [tiers[rank] for rank in sorted(tiers, key=lambda r: r.order)]
        assert ordered == sorted(ordered), slug


def test_every_wired_source_has_a_catalogue_entry():
    """A backfill iterator without an achievement type can never grant."""
    assert set(sources.BACKFILL_ITERATORS) <= set(SEED_SLUGS)


def test_automatic_slugs_are_derived_from_the_iterators():
    """The CLI --source choices cannot drift from the wired iterators."""
    assert sources.AUTOMATIC_SLUGS == [
        slug.value for slug in sources.BACKFILL_ITERATORS
    ]


@pytest.mark.django_db
def test_seed_catalogue_creates_the_whole_taxonomy(catalogue):
    """Seeding produces one achievement and badge per entry, with five tiers."""
    assert Achievement.objects.count() == len(SEED_CATALOGUE)
    assert Badge.objects.count() == len(SEED_CATALOGUE)
    assert BadgeTier.objects.count() == len(SEED_CATALOGUE) * len(TierRank)

    for slug, name, _description, label, tiers in SEED_CATALOGUE:
        badge = Badge.objects.get(label=label)
        assert badge.achievement.slug == slug
        assert badge.achievement.name == name
        assert {(tier.rank, tier.threshold) for tier in badge.tiers.all()} == {
            (rank.value, threshold) for rank, threshold in tiers.items()
        }


@pytest.mark.django_db
def test_seed_catalogue_is_idempotent(catalogue):
    """Re-seeding an already-seeded database creates nothing new."""
    seed_catalogue(Achievement, Badge, BadgeTier)

    assert Achievement.objects.count() == len(SEED_CATALOGUE)
    assert Badge.objects.count() == len(SEED_CATALOGUE)
    assert BadgeTier.objects.count() == len(SEED_CATALOGUE) * len(TierRank)
    assert not (
        Badge.objects.values("label").annotate(n=Count("id")).filter(n__gt=1).exists()
    )


@pytest.mark.django_db
def test_seeded_slugs_match_the_enum(catalogue):
    """Every slug the codebase refers to resolves to a real row."""
    seeded = set(Achievement.objects.values_list("slug", flat=True))
    assert {slug.value for slug in AchievementSlug} <= seeded


@pytest.mark.django_db
def test_badge_label_is_unique(achievement):
    """Two badges cannot share a label; the profile would render duplicates."""
    baker.make(Badge, label=BadgeLabel.REVIEWER, achievement=achievement)

    with pytest.raises(IntegrityError), transaction.atomic():
        baker.make(Badge, label=BadgeLabel.REVIEWER, achievement=achievement)


@pytest.mark.django_db
def test_seed_catalogue_survives_a_retuned_tier(catalogue):
    """Re-seeding must not trip over the two rows a retune leaves behind.

    The badge admin page retunes a threshold by retiring the old tier and
    creating a replacement, so the rank has two rows. Matching on (badge, rank)
    alone finds both.
    """
    tier = BadgeTier.objects.get(badge__label=BadgeLabel.MAINTAINER, rank=TierRank.GOLD)
    tier.threshold = 99
    replace_tier(tier)
    assert BadgeTier.objects.filter(badge=tier.badge, rank=TierRank.GOLD).count() == 2

    seed_catalogue(Achievement, Badge, BadgeTier)

    rows = BadgeTier.objects.filter(badge=tier.badge, rank=TierRank.GOLD)
    assert rows.count() == 2
    assert rows.get(is_active=True).threshold == 99


@pytest.mark.django_db
def test_seed_catalogue_does_not_resurrect_a_retired_rank(catalogue):
    """A rank staff retired on purpose stays retired through a re-seed."""
    tier = BadgeTier.objects.get(
        badge__label=BadgeLabel.MAINTAINER, rank=TierRank.DIAMOND
    )
    deactivate_tier(tier)

    seed_catalogue(Achievement, Badge, BadgeTier)

    rows = BadgeTier.objects.filter(badge=tier.badge, rank=TierRank.DIAMOND)
    assert rows.count() == 1
    assert rows.get().is_active is False
