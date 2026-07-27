import datetime

import pytest
from django.template.loader import render_to_string

from core.constants import BadgeToken

from ..achievements import (
    boost_day_badge,
    is_boost_day,
    profile_badges,
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


@pytest.mark.parametrize(
    "joined,today,expected",
    [
        # Anniversary of a member who has been here a year or more.
        (datetime.date(2020, 6, 15), datetime.date(2026, 6, 15), True),
        (datetime.date(2020, 6, 15), datetime.date(2026, 6, 14), False),
        (datetime.date(2020, 6, 15), datetime.date(2026, 7, 15), False),
        # Never on the sign-up day itself, only from the first anniversary.
        (datetime.date(2026, 6, 15), datetime.date(2026, 6, 15), False),
        (datetime.date(2025, 6, 15), datetime.date(2026, 6, 15), True),
        # Feb 29 sign-ups celebrate on Mar 1 in non-leap years, Feb 29 in leap years.
        (datetime.date(2024, 2, 29), datetime.date(2025, 3, 1), True),
        (datetime.date(2024, 2, 29), datetime.date(2025, 2, 28), False),
        (datetime.date(2024, 2, 29), datetime.date(2028, 2, 29), True),
        (datetime.date(2024, 2, 29), datetime.date(2028, 3, 1), False),
    ],
)
def test_is_boost_day(joined, today, expected):
    assert is_boost_day(joined, today) is expected


def test_is_boost_day_without_join_date():
    assert is_boost_day(None, datetime.date(2026, 6, 15)) is False


def test_boost_day_badge_off_anniversary():
    joined = datetime.date(2020, 6, 15)
    assert boost_day_badge(joined, datetime.date(2026, 6, 14)) is None


@pytest.mark.parametrize(
    "joined,today,expected_label",
    [
        (datetime.date(2025, 6, 15), datetime.date(2026, 6, 15), "Happy 1st Boost Day"),
        (datetime.date(2024, 6, 15), datetime.date(2026, 6, 15), "Happy 2nd Boost Day"),
        (datetime.date(2023, 6, 15), datetime.date(2026, 6, 15), "Happy 3rd Boost Day"),
        (
            datetime.date(2016, 6, 15),
            datetime.date(2026, 6, 15),
            "Happy 10th Boost Day",
        ),
        (
            datetime.date(2015, 6, 15),
            datetime.date(2026, 6, 15),
            "Happy 11th Boost Day",
        ),
        (
            datetime.date(2004, 6, 15),
            datetime.date(2026, 6, 15),
            "Happy 22nd Boost Day",
        ),
    ],
)
def test_boost_day_badge_ordinal_label(joined, today, expected_label):
    badge = boost_day_badge(joined, today)
    assert badge == {"token": "boost-day", "label": expected_label}


def test_profile_badges_both_on_anniversary():
    joined = datetime.date(2010, 6, 15)
    assert profile_badges(joined, datetime.date(2026, 6, 15)) == [
        {"token": "star-tier-4", "label": "Boost Member for 16 years"},
        {"token": "boost-day", "label": "Happy 16th Boost Day"},
    ]


def test_profile_badges_star_only_off_anniversary():
    joined = datetime.date(2010, 6, 15)
    badges = profile_badges(joined, datetime.date(2026, 6, 16))
    assert [b["token"] for b in badges] == ["star-tier-4"]


def test_profile_badges_boost_day_only_before_first_star():
    """A member celebrating their 1st Boost Day has not yet earned a star."""
    joined = datetime.date(2025, 6, 15)
    badges = profile_badges(joined, datetime.date(2026, 6, 15))
    assert [b["token"] for b in badges] == ["boost-day"]


def test_profile_badges_empty_for_new_account():
    joined = datetime.date(2026, 6, 15)
    assert profile_badges(joined, datetime.date(2026, 6, 20)) == []


# Far enough back that the resolved tier stays the top one as time passes.
LONG_TENURED = datetime.datetime(1990, 1, 1, tzinfo=datetime.timezone.utc)


def test_user_profile_badges(user):
    user.date_joined = LONG_TENURED
    assert [b["token"] for b in user.profile_badges] == ["star-tier-5"]


def test_user_profile_badges_empty_for_new_account(user):
    assert user.profile_badges == []


def test_to_v3_profile_dict_carries_badges(user):
    user.date_joined = LONG_TENURED
    profile = user.to_v3_profile_dict()
    assert profile["profile_badges"][0]["token"] == "star-tier-5"
    assert profile["profile_badges"][0]["label"].startswith("Boost Member for ")


def test_to_v3_profile_dict_without_badges(user):
    assert user.to_v3_profile_dict()["profile_badges"] == []


def test_user_profile_template_renders_raw_user(user):
    """Templates pass Entry.author straight through, so `author` may be a User.

    The context key must stay `profile_badges`; `badges` resolves to the
    User.badges m2m manager and blows up the {% for %} loop.
    """
    user.date_joined = LONG_TENURED
    html = render_to_string("v3/includes/_user_profile.html", {"author": user})
    assert "user-profile__badges" in html
    assert "star-tier-5.png" in html
