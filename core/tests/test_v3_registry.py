"""Drift checks for V3 views.

V3 views are discovered automatically by walking Django's URL resolver
and finding every `V3Mixin` subclass — no manual list to maintain.

Two tests run against the discovered set: one verifies at least one V3 view
exists, and a parametrized one verifies template paths are valid.

This whole module gets deleted when the migration ends — see
`config/v3_urls.py` for teardown steps.
"""

from __future__ import annotations

import pytest
from django.template import TemplateDoesNotExist
from django.template.loader import get_template

from core.mixins import iter_v3_views


def _get_v3_view_classes() -> set[type]:
    return {view_class for _, view_class in iter_v3_views()}


def _get_v3_view_classes_with_template() -> set[type]:
    return {
        view_class
        for view_class in _get_v3_view_classes()
        if getattr(view_class, "v3_template_name", None)
    }


@pytest.fixture(scope="session")
def v3_view_classes():
    return sorted(_get_v3_view_classes(), key=lambda c: c.__name__)


def test_v3_views_discovered(v3_view_classes):
    """The resolver must find at least one V3 view."""
    assert v3_view_classes, "No V3Mixin subclasses found in URL conf"


@pytest.mark.parametrize(
    "view_class",
    _get_v3_view_classes_with_template(),
    ids=lambda c: c.__name__,
)
def test_v3_template_exists(view_class):
    """Every V3 view that declares a template must point to a real one.

    Views that opt out of v3 rendering (`v3_template_name = None`, e.g.
    EntryModerationDetailView) are excluded from this check but still
    surface in `iter_v3_views()` so the V3 Demo registry can list them.
    """
    template = view_class.v3_template_name
    try:
        get_template(template)
    except TemplateDoesNotExist:
        pytest.fail(f"{view_class.__name__}: template {template!r} not found")
