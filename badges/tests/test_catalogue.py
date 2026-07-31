"""Consistency tests for the achievement / badge taxonomy.

``Achievement.slug`` is an open field by design (admins may add manual-only
types), so the slugs the codebase hard-codes are only safe if something checks
they still exist. These tests are that check: they cover the seams between
``badges.enums`` and ``badges.catalogue``.
"""

import pytest
from django.db import IntegrityError, transaction
from django.db.models import Count
from model_bakery import baker

from badges.catalogue import CATALOGUE, seed_catalogue
from badges.enums import AchievementSlug, BadgeLabel, TierRank
from badges.models import Achievement, Badge, BadgeTier
from badges.services import deactivate_tier, replace_tier

CATALOGUE_SLUGS = [entry[0] for entry in CATALOGUE]
CATALOGUE_LABELS = [entry[3] for entry in CATALOGUE]


def test_every_catalogue_entry_uses_the_enums():
    """No raw strings in the catalogue: slugs, labels and ranks are all enums."""
    for slug, _name, _description, label, tiers in CATALOGUE:
        assert isinstance(slug, AchievementSlug)
        assert isinstance(label, BadgeLabel)
        for rank in tiers:
            assert isinstance(rank, TierRank)


def test_catalogue_slugs_and_labels_are_unique():
    """One achievement type per slug, one badge per label."""
    assert len(CATALOGUE_SLUGS) == len(set(CATALOGUE_SLUGS))
    assert len(CATALOGUE_LABELS) == len(set(CATALOGUE_LABELS))


def test_catalogue_covers_every_enum_member():
    """Adding an enum member without a catalogue entry is a mistake."""
    assert set(CATALOGUE_SLUGS) == set(AchievementSlug)
    assert set(CATALOGUE_LABELS) == set(BadgeLabel)


def test_every_catalogue_entry_defines_every_rank():
    """A badge with a missing rank would silently skip that tier."""
    for slug, _name, _description, _label, tiers in CATALOGUE:
        assert set(tiers) == set(TierRank), slug


def test_thresholds_increase_with_rank():
    """A lower rank must not need more achievements than a higher one."""
    for slug, _name, _description, _label, tiers in CATALOGUE:
        ordered = [tiers[rank] for rank in sorted(tiers, key=lambda r: r.order)]
        assert ordered == sorted(ordered), slug


@pytest.mark.django_db
def test_seed_catalogue_creates_the_whole_taxonomy(catalogue):
    """Seeding produces one achievement and badge per entry, with five tiers."""
    assert Achievement.objects.count() == len(CATALOGUE)
    assert Badge.objects.count() == len(CATALOGUE)
    assert BadgeTier.objects.count() == len(CATALOGUE) * len(TierRank)

    for slug, name, _description, label, tiers in CATALOGUE:
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

    assert Achievement.objects.count() == len(CATALOGUE)
    assert Badge.objects.count() == len(CATALOGUE)
    assert BadgeTier.objects.count() == len(CATALOGUE) * len(TierRank)
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
