"""Tenure star badge resolution.

The badge is derived from the member's account creation date at render
time — nothing is stored and no scheduled job assigns it.
"""

from datetime import date, datetime

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
