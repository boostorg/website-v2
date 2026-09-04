import json
from datetime import date, timedelta

from ..templatetags.date_filters import years_since
from ..templatetags.number_filters import compact_number, k_count
from ..templatetags.text_helpers import to_json


def test_years_since():
    # Test case for exactly 2 years
    assert years_since(date.today() - timedelta(days=2 * 365)) == 2

    # Test case for less than a year
    assert years_since(date.today() - timedelta(days=100)) == 0

    # Test case for 1.5 years (it should round down)
    assert years_since(date.today() - timedelta(days=int(1.5 * 365))) == 1

    # Test case for 2.9 years (it should still round down)
    assert years_since(date.today() - timedelta(days=int(2.9 * 365))) == 2


def test_to_json_empty():
    assert to_json([]) == "[]"
    assert to_json(None) == "[]"


def test_to_json_tuples():
    result = json.loads(to_json([("us", "United States"), ("ca", "Canada")]))
    assert result == [
        {"value": "us", "label": "United States"},
        {"value": "ca", "label": "Canada"},
    ]


def test_to_json_dicts_passthrough():
    options = [{"value": "a", "label": "Alpha"}]
    assert json.loads(to_json(options)) == options


def test_to_json_escapes_html_special_chars():
    raw = to_json([{"value": "<x>", "label": "a&b"}])
    assert "<" not in raw
    assert ">" not in raw
    assert "&" not in raw
    assert json.loads(raw) == [{"value": "<x>", "label": "a&b"}]


def test_to_json_prevents_script_injection():
    raw = to_json([{"value": "x", "label": "</script><script>alert(1)"}])
    assert "</script>" not in raw


def test_k_count_pads_single_digits():
    """The counter keeps one width, so 1..9 are shown as 01..09."""
    assert [k_count(n) for n in (0, 1, 9)] == ["00", "01", "09"]


def test_k_count_leaves_wider_numbers_alone():
    assert [k_count(n) for n in (10, 99, 999)] == ["10", "99", "999"]


def test_k_count_still_uses_the_k_dimension():
    assert [k_count(n) for n in (1000, 5500, 10000)] == ["1K", "5.5K", "10K"]


def test_k_count_rounds_five_digit_counts_to_whole_thousands():
    """A decimal makes five digits too wide for the counter, so it is dropped."""
    assert [k_count(n) for n in (29200, 29500, 29999)] == ["29K", "30K", "30K"]


def test_k_count_rounds_half_up():
    """Not half to even, which would make 28500 round down while 29500 rounds up."""
    assert [k_count(n) for n in (28500, 29500)] == ["29K", "30K"]


def test_k_count_keeps_the_decimal_below_five_digits():
    assert [k_count(n) for n in (1000, 5500, 9999)] == ["1K", "5.5K", "10K"]


def test_compact_number_rounds_five_digit_counts_to_whole_thousands():
    assert [compact_number(n) for n in (29200, 29500, 28500)] == ["29k", "30k", "29k"]


def test_compact_number_leaves_the_other_dimensions_alone():
    values = (999, 2300, 9999, 100000, 1500000)
    assert [compact_number(n) for n in values] == [
        "999",
        "2.3k",
        "10k",
        "100k",
        "1.5M",
    ]


def test_compact_number_rounds_six_digit_counts_too():
    """The decimal is dropped from five digits up, not only at five."""
    values = (101999, 191029, 101400, 101500)
    assert [compact_number(n) for n in values] == ["102k", "191k", "101k", "102k"]
