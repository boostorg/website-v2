"""Tenure star and Boost Day badge resolution.

Both badges are derived from the member's account creation date at render
time — nothing is stored and no scheduled job assigns them.
"""

import calendar
from datetime import date, datetime

from django.contrib.humanize.templatetags.humanize import ordinal
from django.utils import timezone

from core.constants import BadgeToken

TENURE_TIERS = (
    (2, BadgeToken.STAR_TIER_1),  # bronze
    (5, BadgeToken.STAR_TIER_2),  # silver
    (10, BadgeToken.STAR_TIER_3),  # gold
    (15, BadgeToken.STAR_TIER_4),  # diamond
    (20, BadgeToken.STAR_TIER_5),  # platinum
)


def _as_local_date(value):
    """Normalise a date/datetime (aware or naive) to a local date."""
    if value is None:
        return None
    # datetime subclasses date, so it has to be checked first.
    if isinstance(value, datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        return value.date()
    if isinstance(value, date):
        return value
    return None


def tenure_years(joined, today=None):
    """Full years elapsed since `joined`, floored at 0."""
    joined = _as_local_date(joined)
    if joined is None:
        return 0
    today = today or timezone.localdate()
    years = today.year - joined.year
    if (today.month, today.day) < (joined.month, joined.day):
        years -= 1
    return max(years, 0)


def tenure_tier_token(years):
    """Highest tenure star earned at `years`, or None below the first tier."""
    token = None
    for minimum, tier_token in TENURE_TIERS:
        if years >= minimum:
            token = tier_token
    return token


def is_boost_day(joined, today=None):
    """True on the calendar anniversary of `joined`, first anniversary onward.

    Members who signed up on February 29th celebrate on March 1st in
    non-leap years.
    """
    joined = _as_local_date(joined)
    if joined is None:
        return False
    today = today or timezone.localdate()
    if tenure_years(joined, today) < 1:
        return False
    if (joined.month, joined.day) == (2, 29) and not calendar.isleap(today.year):
        return (today.month, today.day) == (3, 1)
    return (today.month, today.day) == (joined.month, joined.day)


def tenure_badge(joined, today=None):
    """Tenure star badge dict, or None for members under 2 years."""
    years = tenure_years(joined, today)
    token = tenure_tier_token(years)
    if token is None:
        return None
    return {
        "token": str(token),
        "label": f"Boost Member for {years} years",
    }


def boost_day_badge(joined, today=None):
    """Boost Day badge dict, or None when today is not the anniversary."""
    if not is_boost_day(joined, today):
        return None
    return {
        "token": str(BadgeToken.BOOST_DAY),
        "label": f"Happy {ordinal(tenure_years(joined, today))} Boost Day",
    }


def profile_badges(joined, today=None):
    """Both badges keyed by slot, matching Figma node 5942:11222.

    The tenure medal sits beside the member's role, the Boost Day icon
    beside their name.
    """
    today = today or timezone.localdate()
    return {
        "tenure_badge": tenure_badge(joined, today),
        "boost_day_badge": boost_day_badge(joined, today),
    }
