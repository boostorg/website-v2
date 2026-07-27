import datetime

import pytest

from core.constants import BadgeToken

from ..achievements import (
    tenure_badge,
    tenure_tier_token,
    tenure_years,
)


@pytest.mark.parametrize(
    "joined,today,expected",
    [
        # Anniversary day counts, the day before does not.
        (datetime.date(2020, 6, 15), datetime.date(2026, 6, 15), 6),
        (datetime.date(2020, 6, 15), datetime.date(2026, 6, 14), 5),
        (datetime.date(2020, 6, 15), datetime.date(2026, 6, 16), 6),
        # Same day, and a join date in the future, both floor at 0.
        (datetime.date(2026, 6, 15), datetime.date(2026, 6, 15), 0),
        (datetime.date(2027, 1, 1), datetime.date(2026, 6, 15), 0),
        # Feb 29 sign-ups tick over on Mar 1 in non-leap years.
        (datetime.date(2024, 2, 29), datetime.date(2025, 2, 28), 0),
        (datetime.date(2024, 2, 29), datetime.date(2025, 3, 1), 1),
        (datetime.date(2024, 2, 29), datetime.date(2028, 2, 29), 4),
    ],
)
def test_tenure_years(joined, today, expected):
    assert tenure_years(joined, today) == expected


def test_tenure_years_accepts_aware_datetime():
    joined = datetime.datetime(2020, 6, 15, 12, 0, tzinfo=datetime.timezone.utc)
    assert tenure_years(joined, datetime.date(2026, 6, 15)) == 6


def test_tenure_years_without_join_date():
    assert tenure_years(None, datetime.date(2026, 6, 15)) == 0


@pytest.mark.parametrize(
    "years,expected",
    [
        (0, None),
        (1, None),
        (2, BadgeToken.STAR_TIER_1),
        (4, BadgeToken.STAR_TIER_1),
        (5, BadgeToken.STAR_TIER_2),
        (9, BadgeToken.STAR_TIER_2),
        (10, BadgeToken.STAR_TIER_3),
        (14, BadgeToken.STAR_TIER_3),
        (15, BadgeToken.STAR_TIER_4),
        (19, BadgeToken.STAR_TIER_4),
        (20, BadgeToken.STAR_TIER_5),
        (99, BadgeToken.STAR_TIER_5),
    ],
)
def test_tenure_tier_token(years, expected):
    assert tenure_tier_token(years) == expected


def test_tenure_badge_below_first_tier():
    joined = datetime.date(2025, 6, 15)
    assert tenure_badge(joined, datetime.date(2026, 6, 15)) is None


def test_tenure_badge_token_and_label():
    joined = datetime.date(2019, 6, 15)
    assert tenure_badge(joined, datetime.date(2026, 6, 15)) == {
        "token": "star-tier-2",
        "label": "Boost Member for 7 years",
    }


def test_tenure_badge_reflects_highest_tier_reached():
    joined = datetime.date(2001, 1, 1)
    badge = tenure_badge(joined, datetime.date(2026, 6, 15))
    assert badge["token"] == "star-tier-5"
    assert badge["label"] == "Boost Member for 25 years"


# Far enough back that the resolved tier stays the top one as time passes.
LONG_TENURED = datetime.datetime(1990, 1, 1, tzinfo=datetime.timezone.utc)


def test_user_tenure_badge(user):
    user.date_joined = LONG_TENURED
    assert user.tenure_badge["token"] == "star-tier-5"


def test_user_tenure_badge_none_for_new_account(user):
    assert user.tenure_badge is None


def test_to_v3_profile_dict_carries_badge(user):
    user.date_joined = LONG_TENURED
    profile = user.to_v3_profile_dict()
    assert profile["badge"] == "star-tier-5"
    assert profile["badge_label"].startswith("Boost Member for ")


def test_to_v3_profile_dict_without_badge(user):
    profile = user.to_v3_profile_dict()
    assert profile["badge"] is None
    assert profile["badge_label"] is None
