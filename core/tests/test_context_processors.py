from types import SimpleNamespace

import pytest
from django.test import RequestFactory
from django.urls import ResolverMatch

from core.context_processors import (
    active_nav_item,
    current_version,
    selected_version,
)
from libraries.constants import SELECTED_BOOST_VERSION_COOKIE_NAME
from versions.managers import HeaderVersionData


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


def _stub_header_data(request):
    most_recent = SimpleNamespace(slug="boost-1-88-0", display_name="1.88.0")
    older = SimpleNamespace(slug="boost-1-87-0", display_name="1.87.0")
    request._header_version_data = HeaderVersionData(
        options=[most_recent, older],
        most_recent=most_recent,
        most_recent_beta=None,
    )
    return most_recent, older


def _attach_resolver(request, *, route, kwargs, view_name=""):
    request.resolver_match = ResolverMatch(
        func=lambda r: None,
        args=(),
        kwargs=kwargs,
        url_name=view_name or None,
        route=route,
    )


def test_selected_version_url_driven_for_boost_route(rf):
    request = rf.get("/releases/1.88.0/")
    most_recent, older = _stub_header_data(request)
    _attach_resolver(
        request,
        route="releases/<boostversionslug:version_slug>/",
        kwargs={"version_slug": "boost-1-88-0"},
        view_name="release-detail",
    )
    ctx = selected_version(request)
    assert ctx["selected_version_is_url_driven"] is True
    assert ctx["selected_version_is_non_latest"] is True
    assert ctx["selected_version_label"] == "1.88.0"
    assert ctx["selected_version"] is most_recent
    assert ctx["latest_href"] == "/releases/latest/"
    assert most_recent.href == "/releases/1.88.0/"
    assert older.href == "/releases/1.87.0/"


def test_selected_version_url_driven_with_latest_slug(rf):
    """`/releases/latest/` is URL-driven but the label should still read
    'Latest' and the version should fall back to most_recent."""
    request = rf.get("/releases/latest/")
    most_recent, _ = _stub_header_data(request)
    _attach_resolver(
        request,
        route="releases/<boostversionslug:version_slug>/",
        kwargs={"version_slug": "latest"},
        view_name="release-detail",
    )
    ctx = selected_version(request)
    assert ctx["selected_version_is_url_driven"] is True
    assert ctx["selected_version_is_non_latest"] is False
    assert ctx["selected_version_label"] == "Latest"
    assert ctx["selected_version"] is most_recent


def test_selected_version_cookie_driven(rf):
    """Cookie mode: no URL slug, cookie picks the version, dropdown renders
    POST forms (no `latest_href`, no per-option `.href`)."""
    request = rf.get("/")
    request.COOKIES[SELECTED_BOOST_VERSION_COOKIE_NAME] = "boost-1-87-0"
    _, older = _stub_header_data(request)
    ctx = selected_version(request)
    assert ctx["selected_version_is_url_driven"] is False
    assert ctx["selected_version_is_non_latest"] is True
    assert ctx["selected_version_label"] == "1.87.0"
    assert ctx["selected_version"] is older
    assert ctx["latest_href"] == ""


def test_selected_version_ignores_foreign_route_with_same_kwarg(rf):
    """A route declaring `version_slug` via a different converter must NOT be
    treated as URL-driven — the guard against silent coupling."""
    request = rf.get("/elsewhere/anything/")
    _stub_header_data(request)
    _attach_resolver(
        request,
        route="elsewhere/<str:version_slug>/",
        kwargs={"version_slug": "anything"},
        view_name="some-other-view",
    )
    ctx = selected_version(request)
    assert ctx["selected_version_is_url_driven"] is False
    assert ctx["selected_version_label"] == "Latest"


def test_selected_version_no_resolver_match(rf):
    request = rf.get("/")
    _stub_header_data(request)
    ctx = selected_version(request)
    assert ctx["selected_version_is_url_driven"] is False
    assert ctx["selected_version_label"] == "Latest"
