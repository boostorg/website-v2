"""Drift checks for the V3 migration registry.

`V3_VIEWS` below is the canonical list of views taking part in the V3
migration. Two parametrized tests run against it to keep template paths
and `V3Mixin` / `v3_status` usage in sync. See each test's docstring
for what it catches and why.

To add a new V3 view: set `v3_status` on the class, append the class to
`V3_VIEWS`, and run this test file. This whole module gets deleted when
the migration ends — see `config/v3_urls.py` for teardown steps.
"""

from __future__ import annotations

import pytest
from django.template import TemplateDoesNotExist
from django.template.loader import get_template

from core.mixins import V3Mixin
from core.v3_registry import V3Status
from core.views import (
    CalendarView,
    LearnPageView,
    PrivacyPolicyView,
    TermsOfUseView,
    V3ComponentDemoView,
)
from news.views import V3AllTypesCreateView


# Add new V3 views here as they are created. This is the canonical list of views taking part in the
# V3 migration, and the tests below rely on it to find all relevant classes.
V3_VIEWS: tuple[type, ...] = (
    CalendarView,
    PrivacyPolicyView,
    TermsOfUseView,
    LearnPageView,
    V3ComponentDemoView,
    V3AllTypesCreateView,
)


def _effective_template(view_class: type) -> str | None:
    """Return the template that is rendered for the V3 experience.

    Which attribute holds that template depends on the view's migration
    status:

    * `V3_OPTIONAL` — the view uses `V3Mixin` (see `core/mixins.py`) and
      keeps its *legacy* template in `template_name`. The V3 template
      lives under `v3_template_name` and is only rendered when the `v3`
      waffle flag is active.
    * `V3_ONLY` / `V3_PARALLEL` — there is no legacy/V3 switch on the
      view; it renders a single V3 template, which lives in the normal
      `template_name` attribute.
    * Any other status — this helper has nothing to verify.
    """
    status = getattr(view_class, "v3_status", V3Status.LEGACY_ONLY)
    if status == V3Status.V3_OPTIONAL:
        return getattr(view_class, "v3_template_name", None)
    if status in (V3Status.V3_ONLY, V3Status.V3_PARALLEL):
        return getattr(view_class, "template_name", None)
    return None


@pytest.mark.parametrize("view_class", V3_VIEWS, ids=lambda c: c.__name__)
def test_v3_template_exists(view_class):
    """Every V3 view must point to a template that Django can load.

    What this catches
    -----------------
    * Typos in `v3_template_name` (e.g. `"v3/calender.html"`).
    * Templates that were renamed or deleted without updating the view.
    * Forgetting to set `v3_template_name` at all on a `V3_OPTIONAL` view.

    How it works
    ------------
    Parametrized over `V3_VIEWS` (one test per view, so failures are
    attributed to the offending class in pytest output). For each view,
    `_effective_template` picks the right attribute based on status and
    we resolve that name through `django.template.loader.get_template`.
    The loader consults every configured template directory, so this
    mirrors exactly what Django does at request time.

    Why it matters
    --------------
    Without this check, a broken V3 template path only surfaces when a
    waffle-flagged user hits the page — which is often the QA team, not
    a developer running the test suite.
    """
    template = _effective_template(view_class)
    assert template, f"{view_class.__name__}: no V3 template set"
    try:
        get_template(template)
    except TemplateDoesNotExist:
        pytest.fail(f"{view_class.__name__}: template {template!r} not found")


@pytest.mark.parametrize("view_class", V3_VIEWS, ids=lambda c: c.__name__)
def test_v3_mixin_and_status_match(view_class):
    """`V3Mixin` usage and `v3_status` must agree on every view.

    Three invariants enforced here
    ------------------------------
    1. **Every view in `V3_VIEWS` has a non-default `v3_status`.** Being
       in this tuple means the view is part of the migration; not setting
       `v3_status` would leave it invisible to grep and to future cleanup
       work.
    2. **`V3_OPTIONAL` ⇒ uses `V3Mixin` and sets `v3_template_name`.**
       `V3_OPTIONAL` means "legacy template by default, V3 template when
       the flag flips." That switch is implemented by `V3Mixin`; without
       it, setting the status is a lie.
    3. **Uses `V3Mixin` ⇒ `v3_status == V3_OPTIONAL`.** This is the
       *other* direction of the same check. Without it, a view could be
       promoted to `V3_ONLY` (removing the legacy template) while still
       inheriting from `V3Mixin` — leaving dead scaffolding in the class.

    Why the check is bidirectional
    ------------------------------
    A one-way check would let either half of the pair drift silently.
    The whole point of `v3_status` is that it stays honest throughout
    the migration, so both directions are verified.
    """
    status = getattr(view_class, "v3_status", V3Status.LEGACY_ONLY)
    is_mixin = issubclass(view_class, V3Mixin)

    # Invariant 1: view is actually tagged as part of the migration.
    assert (
        status != V3Status.LEGACY_ONLY
    ), f"{view_class.__name__} is in V3_VIEWS but has no v3_status attribute"

    # Invariant 2: V3_OPTIONAL requires V3Mixin + v3_template_name.
    if status == V3Status.V3_OPTIONAL:
        assert is_mixin, (
            f"{view_class.__name__} has v3_status=V3_OPTIONAL but does not "
            "inherit from V3Mixin"
        )
        assert getattr(view_class, "v3_template_name", None), (
            f"{view_class.__name__} has v3_status=V3_OPTIONAL but no "
            "v3_template_name"
        )

    # Invariant 3: V3Mixin is only valid alongside V3_OPTIONAL.
    if is_mixin:
        assert status == V3Status.V3_OPTIONAL, (
            f"{view_class.__name__} uses V3Mixin but v3_status={status.value}; "
            "expected V3_OPTIONAL"
        )
