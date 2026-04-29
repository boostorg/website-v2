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


@pytest.fixture(scope="session")
def v3_view_classes():
    return sorted(_get_v3_view_classes(), key=lambda c: c.__name__)


def test_v3_views_discovered(v3_view_classes):
    """The resolver must find at least one V3 view."""
    assert v3_view_classes, "No V3Mixin subclasses found in URL conf"


@pytest.mark.parametrize(
    "view_class",
    _get_v3_view_classes(),
    ids=lambda c: c.__name__,
)
def test_v3_template_exists(view_class):
    """Every V3 view must point to a `v3_template_name` that Django can load."""
    template = getattr(view_class, "v3_template_name", None)
    assert template, f"{view_class.__name__}: no v3_template_name set"
    try:
        get_template(template)
    except TemplateDoesNotExist:
        pytest.fail(f"{view_class.__name__}: template {template!r} not found")
