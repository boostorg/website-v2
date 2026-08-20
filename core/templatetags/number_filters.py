"""
Template filters for number formatting.
"""

from django import template

register = template.Library()


@register.filter
def compact_number(value):
    """
    Format integers in compact form: 2300 → 2.3k, 33000 → 33k, 1500000 → 1.5M.
    Values under 1000 are shown as-is. Non-numeric values are returned unchanged.
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
        k = n / 1000
        formatted = f"{k:.1f}".rstrip("0").rstrip(".")
        return f"{formatted}k"
    m = n / 1_000_000
    formatted = f"{m:.1f}".rstrip("0").rstrip(".")
    return f"{formatted}M"


@register.filter
def k_count(value):
    """
    Achievement-counter format per Figma spec: a single digit is padded to two
    so the counter keeps one width — e.g. 1 → "01", 9 → "09" — 10..999 are shown
    as-is, and 1000+ uses the "K" dimension: 1000 → "1K", 5500 → "5.5K".
    Non-numeric values are returned unchanged.
    """
    if value is None:
        return ""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return value
    if n < 1000:
        return f"{n:02d}" if 0 <= n < 10 else str(n)
    k = n / 1000
    formatted = f"{k:.1f}".rstrip("0").rstrip(".")
    return f"{formatted}K"
