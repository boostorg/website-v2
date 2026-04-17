"""Drift checks for V3 views.

V3 views are discovered automatically by walking Django's URL resolver
and finding every `V3Mixin` subclass — no manual list to maintain. Two
parametrized tests run against the discovered set to verify template
paths are valid.

This whole module gets deleted when the migration ends — see
`config/v3_urls.py` for teardown steps.
"""

from __future__ import annotations

import pytest
from django.template import TemplateDoesNotExist
from django.template.loader import get_template
from django.urls import URLPattern, URLResolver, get_resolver

from core.mixins import V3Mixin


def _get_v3_view_classes() -> set[type]:
    """Find all `V3Mixin` subclasses registered in the URL conf.

    Django's URL resolver imports every view module when it resolves
    routes, so this is guaranteed to find all wired-up V3 views —
    no manual registration needed.
    """
    classes: set[type] = set()

    def walk(patterns):
        for entry in patterns:
            if isinstance(entry, URLResolver):
                walk(entry.url_patterns)
            elif isinstance(entry, URLPattern):
                # Unwrap decorators like staff_member_required
                callback = entry.callback
                while callback is not None:
                    view_class = getattr(callback, "view_class", None)
                    if view_class is not None:
                        break
                    callback = getattr(callback, "__wrapped__", None)
                if view_class and issubclass(view_class, V3Mixin):
                    classes.add(view_class)

    walk(get_resolver().url_patterns)
    return classes


@pytest.fixture(scope="session")
def v3_view_classes():
    return sorted(_get_v3_view_classes(), key=lambda c: c.__name__)


def _effective_template(view_class: type) -> str | None:
    """Return the template rendered for the V3 experience.

    All V3 views declare their V3 template via `v3_template_name`
    (see `core/mixins.py`).
    """
    return getattr(view_class, "v3_template_name", None)


def test_v3_views_discovered(v3_view_classes):
    """The resolver must find at least one V3 view.

    If this fails, either no V3 views exist or the resolver walk is
    broken — both worth knowing immediately. Prints the full discovered
    set so you can eyeball it when running with `-s`.
    """
    assert v3_view_classes, "No V3Mixin subclasses found in URL conf"
    print(f"\n  Discovered {len(v3_view_classes)} V3 views:")
    for cls in v3_view_classes:
        template = getattr(cls, "v3_template_name", "—")
        print(f"    {cls.__name__:<30} template={template}")


@pytest.mark.parametrize(
    "view_class",
    _get_v3_view_classes(),
    ids=lambda c: c.__name__,
)
def test_v3_template_exists(view_class):
    """Every V3 view must point to a template that Django can load.

    What this catches
    -----------------
    * Typos in `v3_template_name` (e.g. `"v3/calender.html"`).
    * Templates that were renamed or deleted without updating the view.
    * Forgetting to set `v3_template_name` at all.

    How it works
    ------------
    Parametrized over every `V3Mixin` subclass found in the URL conf
    (one test per view, so failures name the offending class). For each
    view, we resolve `v3_template_name` through Django's template loader,
    which consults all configured template directories — mirroring what
    Django does at request time.

    Why it matters
    --------------
    Without this check, a broken V3 template path only surfaces when a
    waffle-flagged user hits the page — which is often the QA team, not
    a developer running the test suite.
    """
    template = _effective_template(view_class)
    assert template, f"{view_class.__name__}: no v3_template_name set"
    try:
        get_template(template)
    except TemplateDoesNotExist:
        pytest.fail(f"{view_class.__name__}: template {template!r} not found")
