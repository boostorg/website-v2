"""
V3 URL Registry
===============

All URLs with the explicit `/v3/` prefix live here.

All V3 views inherit from `V3Mixin` (see `core/mixins.py`). The test
`core/tests/test_v3_registry.py` auto-discovers all `V3Mixin`
subclasses via the URL resolver and verifies their templates exist — no
manual registration needed.

`V3Mixin` handles two cases based on class attributes:

* **Both templates** (`template_name` + `v3_template_name`) — legacy
  template by default, V3 template when the `v3` waffle flag is active.
* **V3 template only** (`v3_template_name`, no `template_name`) —
  returns 404 when the flag is off.

Full-migration procedure
------------------------
The `v3` waffle flag and `V3Mixin` are migration scaffolding.

A. Convert each view that has both templates
     1. Set `template_name` to the V3 template path.
     2. Fold `get_v3_context_data` into `get_context_data`.
     3. Remove `V3Mixin` from the class bases.
     4. Remove `v3_template_name` and `get_v3_context_data`.
     5. Delete the legacy template.

B. Promote each `/v3/` route
   For each route in this file, move it into `config/urls.py` to
   replace the legacy route (or create a permanent route if none
   exists). Delete or rename the V3 view class as appropriate.

C. Remove the flag from templates and JS
   Unwrap every `{% flag "v3" %}` block and drop matching JS gates.

D. Delete the scaffolding
     1. `V3Mixin` from `core/mixins.py`.
     2. `core/tests/test_v3_registry.py`.
     3. The `v3` waffle flag record from the database.
     4. This file and its import in `config/urls.py`.

See `docs/django-waffle-v3-flag.md` for additional flag context.
"""

from django.contrib.admin.views.decorators import staff_member_required
from django.urls import path

from core.views import LearnPageView, V3ComponentDemoView
from news.views import V3AllTypesCreateView, V3PostDetailView
from users.views import V3LoginView, V3SignupView

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
    path(
        "v3/news/entry/<slug:slug>/",
        V3PostDetailView.as_view(),
        name="v3-news-detail",
    ),
    path(
        "v3/accounts/signup/",
        V3SignupView.as_view(),
        name="v3-signup",
    ),
    path(
        "v3/accounts/login/",
        V3LoginView.as_view(),
        name="v3-login",
    ),
]
