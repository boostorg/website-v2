import json
from datetime import date, timedelta

from ..templatetags.date_filters import years_since
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
