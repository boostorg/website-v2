from dataclasses import dataclass
from enum import StrEnum

from django.conf import settings
from django.urls import NoReverseMatch, reverse

from libraries.constants import LATEST_RELEASE_URL_PATH_STR
from libraries.utils import get_version_from_cookie
from versions.models import Version


def _get_header_version_data(request):
    """Per-request shared accessor so `current_version` and `selected_version`
    share one DB fetch within a single request."""
    cached = getattr(request, "_header_version_data", None)
    if cached is not None:
        return cached
    data = Version.objects.get_header_dropdown_data()
    request._header_version_data = data
    return data


def current_version(request):
    """Custom context processor that adds the current release to the context"""
    return {"current_version": _get_header_version_data(request).most_recent}


def selected_version(request):
    """User's active Boost version + data to render the navbar version dropdown.

    Resolution priority for `selected_version`:
    1. URL `version_slug` kwarg (on `/releases/`, `/libraries/`, `/library/` routes)
    2. `boost_version` cookie
    3. Most recent release (fallback)

    When the version comes from the URL, the dropdown renders anchor links that
    swap the version segment of the current path — shareable. Otherwise it
    renders POST forms that write the cookie without navigating.

    Examples
    --------
    GET /releases/1.88.0/  (no cookie)
        selected_version               -> Version(slug="boost-1-88-0")
        selected_version_is_url_driven -> True       (URL mode: render <a>s)
        selected_version_is_explicit   -> True       (button reads "1.88.0")
        selected_version_label         -> "1.88.0"
        version_dropdown_options[i]    -> Version with `.href` attached,
                                          e.g. "/releases/1.89.0/"
        latest_href                    -> "/releases/latest/"

    GET /  (cookie boost_version="boost-1-87-0")
        selected_version               -> Version(slug="boost-1-87-0")
        selected_version_is_url_driven -> False      (cookie mode: render <form>s)
        selected_version_is_explicit   -> True       (button reads "1.87.0")
        selected_version_label         -> "1.87.0"
        version_dropdown_options[i]    -> Version (no `.href` needed)
        latest_href                    -> ""

    GET /  (no cookie)
        selected_version               -> Version.objects.most_recent()
        selected_version_is_url_driven -> False
        selected_version_is_explicit   -> False      (button reads "Latest")
        selected_version_label         -> "Latest"

    GET /library/1.88.0/foo/  (target version "boost-1-70-0" predates "foo")
        version_dropdown_options[…].href for that version
                                       -> "/library/1.70.0/foo/"
                                          (plain version swap; target view
                                          renders the missing-version state)
    """
    url_version_slug = None
    resolver_match = getattr(request, "resolver_match", None)
    if resolver_match:
        url_version_slug = resolver_match.kwargs.get("version_slug")

    is_url_driven = bool(url_version_slug)
    cookie_slug = get_version_from_cookie(request)

    header_data = _get_header_version_data(request)
    options = list(header_data.options)

    resolved_slug = url_version_slug or cookie_slug
    version = None
    if resolved_slug and resolved_slug != LATEST_RELEASE_URL_PATH_STR:
        version = next((v for v in options if v.slug == resolved_slug), None)
        if version is None:
            version = Version.objects.filter(slug=resolved_slug).first()
    if version is None:
        version = header_data.most_recent

    is_explicit_non_latest_url = bool(
        url_version_slug and url_version_slug != LATEST_RELEASE_URL_PATH_STR
    )
    is_explicit_cookie = bool(
        not url_version_slug
        and cookie_slug
        and cookie_slug != LATEST_RELEASE_URL_PATH_STR
    )
    is_explicit = is_explicit_non_latest_url or is_explicit_cookie

    label = version.display_name if (is_explicit and version) else "Latest"

    latest_href = ""
    if is_url_driven and resolver_match and resolver_match.view_name:
        latest_href = _annotate_option_hrefs(
            view_name=resolver_match.view_name,
            url_kwargs=dict(resolver_match.kwargs),
            options=options,
        )

    return {
        "selected_version": version,
        "selected_version_is_url_driven": is_url_driven,
        "selected_version_is_explicit": is_explicit,
        "selected_version_label": label,
        "version_dropdown_options": options,
        "latest_href": latest_href,
    }


def _annotate_option_hrefs(*, view_name, url_kwargs, options):
    """Attach `.href` to each option for the current page; return the latest's.

    The swap is a plain `reverse()` with the option's version substituted in —
    on a library detail page at `/library/1.88.0/foo/`, picking 1.70.0 yields
    `/library/1.70.0/foo/` even if that library didn't exist in 1.70.0. The
    target view is responsible for rendering the empty / "not available" state.

    Examples
    --------
    Current URL /releases/1.88.0/
        view_name  = "release-detail"
        url_kwargs = {"version_slug": "boost-1-88-0"}
        → each option gets .href = "/releases/<that version>/"
        → returns "/releases/latest/"

    Current URL /libraries/1.88.0/grid/containers/
        view_name  = "libraries-list"
        url_kwargs = {"version_slug": "boost-1-88-0",
                      "library_view_str": "grid",
                      "category_slug": "containers"}
        → each option gets .href = "/libraries/<that version>/grid/containers/"
        → returns "/libraries/latest/grid/containers/"
    """
    for v in options:
        try:
            v.href = reverse(view_name, kwargs={**url_kwargs, "version_slug": v.slug})
        except NoReverseMatch:
            v.href = ""

    try:
        return reverse(
            view_name,
            kwargs={**url_kwargs, "version_slug": LATEST_RELEASE_URL_PATH_STR},
        )
    except NoReverseMatch:
        return ""


class NavItem(StrEnum):
    LIBRARIES = "libraries"
    LEARN = "learn"
    NEWS = "news"
    COMMUNITY = "community"
    RELEASES = "releases"


_PATH_MAP = {
    "/doc/libs/": NavItem.LIBRARIES,  # special case - handle first
    "/doc/": NavItem.LEARN,
    "/docs/": NavItem.LEARN,
    "/boost-development/": NavItem.LEARN,
    "/news/": NavItem.NEWS,
    "/community/": NavItem.COMMUNITY,
    "/library/": NavItem.LIBRARIES,
    "/libraries/": NavItem.LIBRARIES,
    "/releases/": NavItem.RELEASES,
}


def _get_active_nav_item(request):
    """Determines the active nav item based on the request path."""
    for prefix, item in _PATH_MAP.items():
        if request.path.startswith(prefix):
            return item
    return "home"


def active_nav_item(request):
    """Custom context processor that adds the active nav item to the context"""
    return {"active_nav_item": _get_active_nav_item(request)}


@dataclass
class NavLink:
    """A single header navigation link."""

    label: str
    url: str
    nav_id: str = ""
    is_unread: bool = False


def header_context(request):
    """Context processor for header nav links."""
    nav_links = [
        NavLink(label="Libraries", url=reverse("libraries"), nav_id="libraries"),
        NavLink(label="Learn", url=reverse("docs"), nav_id="learn"),
        NavLink(label="Community", url=reverse("community"), nav_id="community"),
        NavLink(
            label="Posts", url=reverse("news"), nav_id="news", is_unread=True
        ),  # TODO: update is_unread based on actual unread state
        NavLink(
            label="Download", url=reverse("releases-most-recent"), nav_id="releases"
        ),
    ]
    return {
        "nav_links": nav_links,
        "releases_url": reverse("releases-most-recent"),
    }


def debug(request):
    """
    Adds settings.DEBUG to the context.
    """
    return {"DEBUG": settings.DEBUG}
