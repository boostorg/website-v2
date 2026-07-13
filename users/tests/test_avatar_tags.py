import pytest

from users.templatetags.avatar_tags import (
    collective_author_label,
    is_collective_author,
)


@pytest.mark.parametrize(
    "value,expected",
    [
        ("Various Authors", True),
        ("Various", True),
        ("various authors", True),
        ("  Various Authors", True),
        ("John Various", False),
        ("Variant", False),
        ("", False),
        (None, False),
        (123, False),
    ],
)
def test_is_collective_author(value, expected):
    assert is_collective_author(value) is expected


@pytest.mark.parametrize(
    "value,expected",
    [
        ("Various", "Various Authors"),
        ("various", "Various Authors"),
        ("Various Authors", "Various Authors"),
        ("Jane Doe", "Jane Doe"),
    ],
)
def test_collective_author_label(value, expected):
    assert collective_author_label(value) == expected
