"""
V3 URL Registry
===============

This file contains all URLs with the explicit `/v3/` prefix. Every V3
view declares its migration status via a ``v3_status`` class attribute
(see ``core/v3_registry.py`` for the enum). The canonical list of V3
view classes lives in ``core/tests/test_v3_registry.py`` as ``V3_VIEWS``
— add new V3 views there when you land them; the tests will verify the
declared template exists and that ``V3Mixin`` / ``v3_status`` stay in
sync.

V3Mixin-backed routes (toggle with waffle flag `v3`)
----------------------------------------------------
These legacy paths already render V3 templates when the `v3` waffle flag
is active. No URL changes are required to go live — flip the flag.

    /calendar/        → v3/calendar.html           (CalendarView)
    /privacy/         → v3/privacy_policy.html     (PrivacyPolicyView)
    /terms-of-use/    → v3/terms_of_use.html       (TermsOfUseView)
    /learn-page/      → v3/learn_page.html         (LearnPageView, staff-only)

Explicit /v3/ routes (below)
----------------------------
    /v3/demo/components/   → component showcase (staff-only)
    /v3/demo/learn-page/   → learn-page preview (staff-only)
    /v3/news/add/          → V3AllTypesCreateView (parallel to /news/add/)

Full-migration procedure
------------------------
The `v3` waffle flag and `V3Mixin` are migration scaffolding. "Fully
migrating" means deleting the scaffolding, not leaving the flag on
forever. Order matters — do steps in this sequence to keep the site
working at every commit.

A. Make V3 the only path (per V3Mixin-backed view)
   For each view in core/views.py that uses `V3Mixin`
   (CalendarView, PrivacyPolicyView, TermsOfUseView, LearnPageView):
     1. Set `template_name` to the v3 template path.
     2. Fold any logic from `get_v3_context_data` into `get_context_data`.
     3. Remove `V3Mixin` from the class bases.
     4. Remove `v3_template_name` and `get_v3_context_data`.
     5. For LearnPageView specifically: remove the dispatch override at
        core/views.py:276-279 that returns 404 when the flag is off, and
        add a public `/learn-page/` (or chosen path) URL — there is no
        legacy route for it today.
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
   1. Delete `V3Mixin` from core/mixins.py (file may become empty).
   2. Delete the `v3` waffle flag record from the database/admin.
   3. Update tests that reference the flag (libraries/tests/test_views.py).
   4. Delete this file (config/v3_urls.py) and the
      `from config.v3_urls import v3_urlpatterns` line in config/urls.py.
   5. Remove the `# V3 via waffle flag` inline comments in config/urls.py.

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
