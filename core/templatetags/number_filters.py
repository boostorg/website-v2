"""
Template filters for number formatting.
"""

from django import template

register = template.Library()

# Below this, a count carries one decimal; at or above it the decimal is dropped.
# Five digits is where "29.2k" stops fitting the counter badge, and a decimal buys
# nothing at that magnitude.
DECIMAL_LIMIT = 10_000


def _thousands(n):
    """``n`` in thousands: one decimal below ``DECIMAL_LIMIT``, whole above it."""
    if n >= DECIMAL_LIMIT:
        # Half up. round() and format() round half to even, which would make
        # 28500 -> "28" while 29500 -> "30".
        return str((n + 500) // 1000)
    return f"{n / 1000:.1f}".rstrip("0").rstrip(".")


@register.filter
def compact_number(value):
    """
    Format integers in compact form: 2300 → 2.3k, 33000 → 33k, 1500000 → 1.5M.
    Counts of 10000 and up round to whole thousands — 29200 → 29k, 29500 → 30k,
    101400 → 101k. Values under 1000 are shown as-is. Non-numeric values are
    returned unchanged.
    """
    if value is None:
        return ""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return value
    if n < 1000:
        return str(n)
    if n < 1_000_000:
        return f"{_thousands(n)}k"
    m = n / 1_000_000
    formatted = f"{m:.1f}".rstrip("0").rstrip(".")
    return f"{formatted}M"


@register.filter
def k_count(value):
    """
    Achievement-counter format per Figma spec: a single digit is padded to two
    so the counter keeps one width — e.g. 1 → "01", 9 → "09" — 10..999 are shown
    as-is, and 1000+ uses the "K" dimension: 1000 → "1K", 5500 → "5.5K". Counts
    of 10000 and up round to whole thousands: 29200 → "29K", 29500 → "30K",
    101400 → "101K". Non-numeric values are returned unchanged.
    """
    if value is None:
        return ""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return value
    if n < 1000:
        return f"{n:02d}" if 0 <= n < 10 else str(n)
    return f"{_thousands(n)}K"
