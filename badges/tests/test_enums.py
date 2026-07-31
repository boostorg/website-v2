"""Tests for the badge enums, including the declared rank ordering."""

from badges.enums import BadgeLabel, TierRank


def test_tier_rank_order_follows_declaration():
    assert TierRank.GOLD.order > TierRank.SILVER.order
    assert TierRank.BRONZE.order < TierRank.DIAMOND.order


def test_tier_rank_sorts_low_to_high_by_order():
    shuffled = [TierRank.DIAMOND, TierRank.BRONZE, TierRank.GOLD, TierRank.SILVER]
    assert sorted(shuffled, key=lambda rank: rank.order) == [
        TierRank.BRONZE,
        TierRank.SILVER,
        TierRank.GOLD,
        TierRank.DIAMOND,
    ]


def test_tier_rank_order_is_defined_for_a_value_read_from_the_db():
    assert TierRank("platinum").order == 3


def test_tier_rank_choices_shape():
    assert ("bronze", "Bronze") in TierRank.choices
    assert ("diamond", "Diamond") in TierRank.choices


def test_badge_label_choices_humanize_names():
    choices = dict(BadgeLabel.choices)
    assert choices["library_author"] == "Library Author"
    assert choices["commits_master"] == "Commits Master"
