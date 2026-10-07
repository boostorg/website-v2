"""The v3 stylesheet bundle stands in for the links it replaces.

`yarn build:css` inlines frontend/v3-bundle.css into static/css/bundles/v3.min.css,
and base.html links that one file instead of five when USE_CSS_BUNDLE is set.
The bundle only reproduces the page if the entry file names the same sheets in
the same order as the links, so the last test fails when the two drift apart.
"""

import re
from pathlib import Path

import pytest
from waffle.testutils import override_flag

REPO = Path(__file__).resolve().parents[2]
ENTRY = REPO / "frontend" / "v3-bundle.css"
BUNDLE_HREF = "/static/css/bundles/v3.min.css"
STYLESHEET_HREF = re.compile(r'<link href="(/static/css/[^"]+)" rel="stylesheet"')
IMPORT = re.compile(r'^@import\s+"([^"]+)";', re.MULTILINE)


def _stylesheets(client):
    """Return the site stylesheets in <head>, in order, from a page that adds none."""
    response = client.get("/donate/")
    assert response.status_code == 200
    head = response.content.decode().split("</head>", 1)[0]
    return STYLESHEET_HREF.findall(head)


@pytest.mark.django_db
@override_flag("v3", active=True)
def test_v3_page_links_only_the_bundle(client, settings):
    settings.USE_CSS_BUNDLE = True

    assert _stylesheets(client) == [BUNDLE_HREF]


@pytest.mark.django_db
@override_flag("v3", active=True)
def test_v3_page_links_the_individual_sheets_without_the_bundle(client, settings):
    settings.USE_CSS_BUNDLE = False

    assert _stylesheets(client) == [
        "/static/css/styles.css",
        "/static/css/components.css",
        "/static/css/v3/boostlook-v3.css",
        "/static/css/v3/v3-style-overrides.css",
        "/static/css/v3/components.css",
    ]


@pytest.mark.django_db
@pytest.mark.parametrize("use_bundle", [True, False])
@override_flag("v3", active=False)
def test_legacy_page_ignores_the_bundle(client, settings, use_bundle):
    settings.USE_CSS_BUNDLE = use_bundle

    assert _stylesheets(client) == [
        "/static/css/styles.css",
        "/static/css/components.css",
        "/static/css/boostlook.css",
    ]


@pytest.mark.django_db
@override_flag("v3", active=True)
def test_bundle_entry_matches_the_links_it_replaces(client, settings):
    settings.USE_CSS_BUNDLE = False
    linked = _stylesheets(client)

    imports = IMPORT.findall(ENTRY.read_text())
    bundled = [
        "/" + (ENTRY.parent / path).resolve().relative_to(REPO).as_posix()
        for path in imports
    ]

    assert bundled == linked
