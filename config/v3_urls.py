"""
V3 URL Registry
===============

This file contains all URLs with the explicit `/v3/` prefix.

All V3 views inherit from `V3Mixin` (see `core/mixins.py`). The test
`core/tests/test_v3_registry.py` auto-discovers all `V3Mixin` subclasses
via the URL resolver and verifies their templates exist — no manual
registration needed.

`V3Mixin` handles two cases based on class attributes:

* **Both templates** (`template_name` + `v3_template_name`) — legacy
  template by default, V3 template when the `v3` waffle flag is active.
* **V3 template only** (`v3_template_name`, no `template_name`) —
  returns 404 when the flag is off.

Full-migration procedure
------------------------
The `v3` waffle flag and `V3Mixin` are migration scaffolding. "Fully
migrating" means deleting the scaffolding, not leaving the flag on
forever. Order matters — do steps in this sequence to keep the site
working at every commit.

A. Make V3 the only path (per view that has both templates)
   For each view with both `template_name` and `v3_template_name`:
     1. Set `template_name` to the v3 template path.
     2. Fold any logic from `get_v3_context_data` into `get_context_data`.
     3. Remove `V3Mixin` from the class bases.
     4. Remove `v3_template_name` and `get_v3_context_data`.
   Then delete the legacy templates (e.g. calendar.html, the markdown
   sources for privacy / terms-of-use).

B. Resolve each explicit /v3/ route
   - `/v3/news/add/` → replace `/news/add/` (config/urls.py:309). Swap
     `AllTypesCreateView` for `V3AllTypesCreateView`, then either rename
     the V3 class to take over the original name or keep both.
   - `/v3/demo/learn-page/` → delete once a permanent learn-page URL
     exists from step A.5.
   - `/v3/demo/components/` → keep as a permanent dev styleguide OR
     delete. No production users depend on it.

C. Remove the flag from templates and JS
   Unwrap every `{% flag "v3" %}…{% endflag %}` block (templates/base.html,
   templates/news/form.html, templates/libraries/detail.html, the v3
   wysiwyg includes). Drop the matching JS gates in static/js/v3/ and
   frontend/.

D. Delete the scaffolding
   1. Delete `V3Mixin` from core/mixins.py.
   2. Delete core/tests/test_v3_registry.py.
   3. Delete the `v3` waffle flag record from the database/admin.
   4. Update tests that reference the flag (libraries/tests/test_views.py).
   5. Delete this file (config/v3_urls.py) and the
      `from config.v3_urls import v3_urlpatterns` line in config/urls.py.
   6. Remove the `# V3 via waffle flag` inline comments in config/urls.py.

See docs/django-waffle-v3-flag.md for additional flag context.
"""

from django.contrib.admin.views.decorators import staff_member_required
from django.urls import path

from core.views import LearnPageView, V3ComponentDemoView
from news.views import V3AllTypesCreateView

v3_urlpatterns = [
    path(
        "v3/demo/components/",
        staff_member_required(V3ComponentDemoView.as_view()),
        name="v3-demo-components",
    ),
    path(
        "v3/demo/learn-page/",
        staff_member_required(LearnPageView.as_view()),
        name="v3-learn-page",
    ),
    path(
        "v3/news/add/",
        V3AllTypesCreateView.as_view(),
        name="v3-news-create",
    ),
]
