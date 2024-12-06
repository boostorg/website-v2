import pytest
from django.test import RequestFactory

from core.context_processors import current_version, active_nav_item


def test_current_version_context(
    version, beta_version, inactive_version, old_version, rf
):
    """Test the current_version context processor. Making the other versions
    ensures that the most_recent() method returns the correct version."""
    request = rf.get("/")
    context = current_version(request)
    assert "current_version" in context
    assert context["current_version"] == version


@pytest.mark.parametrize(
    "path,expected_nav_item",
    [
        ("/", "home"),
        ("/doc/libs/", "libraries"),  # Special case
        ("/doc/", "learn"),
        ("/doc/user-guide/index.html", "learn"),
        ("/docs/", "learn"),
        ("/news/", "news"),
        ("/news/blogpost/", "news"),
        ("/news/link/", "news"),
        ("/news/news/", "news"),
        ("/news/poll/", "news"),
        ("/news/video/", "news"),
        ("/news/entry/some-slug/", "news"),
        ("/community/", "community"),
        ("/library/", "libraries"),
        ("/libraries/1.86.0/grid/", "libraries"),
        ("/releases/1.85.0/", "releases"),
        ("/documentation/", "home"),  # Should not match "/doc/"
    ],
)
def test_active_nav_item(path, expected_nav_item):
    """Test the active_nav_item context processor."""
    request = RequestFactory().get(path)
    context = active_nav_item(request)
    assert context["active_nav_item"] == expected_nav_item
