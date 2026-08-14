"""Critical-path tests for the beta feedback tool.

Deliberately minimal — this is temporary beta tooling. Covers only what would
silently lose feedback or open a hole: both submit paths, identity capture, the
screenshot ceiling, the redirect guard, and that the widget and admin render.
"""

import io
import json
import os

import pytest
import waffle.testutils
from django.contrib.auth.models import AnonymousUser
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.signals import got_request_exception
from django.template import Context, Template
from django.test import Client
from django.urls import reverse
from PIL import Image

from feedback.diagnostics import RING_BUFFER_LIMIT, recent_server_errors
from feedback.models import IMAGE_MAX_BYTES, Feedback

pytestmark = pytest.mark.django_db

XHR = {"X-Requested-With": "XMLHttpRequest"}


def png_bytes(pixels):
    """Random-noise PNG, so encoded size tracks pixel count instead of compressing away."""
    image = Image.frombytes("RGB", (pixels, pixels), os.urandom(pixels * pixels * 3))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def url():
    return reverse("feedback")


@pytest.fixture
def payload():
    return {
        "feedback_type": Feedback.Type.BUG,
        "message": "The version dropdown renders behind the header.",
        "page_url": "http://testserver/libraries/",
    }


@pytest.fixture(autouse=True)
def signed_in(client, user):
    """Every path requires an account; the signed-out tests use their own client."""
    client.force_login(user)
    return user


def test_submission_attaches_the_logged_in_user(client, url, payload, user):
    response = client.post(url, payload, headers=XHR)

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    feedback = Feedback.objects.get()
    assert feedback.user == user
    assert feedback.status == Feedback.Status.NEW


def test_signed_out_submission_is_refused(url, payload):
    """Beta access is gated on an account, so there is no anonymous path."""
    response = Client().post(url, payload, headers=XHR)

    assert response.status_code == 401
    assert not Feedback.objects.exists()


def test_signed_out_visitor_is_sent_to_log_in(url):
    response = Client().get(url)

    assert response.status_code == 302
    assert response.url.startswith("/accounts/login/")


def test_screenshot_is_stored_with_the_feedback(client, url, payload):
    screenshot = SimpleUploadedFile("shot.png", png_bytes(10), "image/png")

    response = client.post(url, {**payload, "image": screenshot}, headers=XHR)

    assert response.status_code == 200
    assert Feedback.objects.get().image.name.startswith("feedback/")


def test_oversized_screenshot_is_rejected(client, url, payload):
    content = png_bytes(900)
    assert len(content) >= IMAGE_MAX_BYTES, "fixture must exceed the ceiling"
    screenshot = SimpleUploadedFile("huge.png", content, "image/png")

    response = client.post(url, {**payload, "image": screenshot}, headers=XHR)

    assert response.status_code == 400
    assert "image" in response.json()["errors"]
    assert not Feedback.objects.exists()


def test_longest_category_slug_fits_the_column(client, url, payload):
    """`incorrect_information` is 21 chars — it overflowed the original max_length=20."""
    category = Feedback.Type.INCORRECT_INFORMATION

    response = client.post(url, {**payload, "feedback_type": category}, headers=XHR)

    assert response.status_code == 200
    assert Feedback.objects.get().feedback_type == category


def test_no_js_submission_refuses_to_redirect_off_site(client, url, payload):
    """page_url is client-supplied, so it must not become an open redirect."""
    response = client.post(url, {**payload, "page_url": "https://evil.example.com/"})

    assert response.status_code == 302
    assert response.url == "/"


def test_route_and_version_are_derived_from_the_page_url(client, url, payload):
    """Server-derived, so reports group by route and cannot be spoofed by the client."""
    page = "http://testserver/library/1.88.0/beast/"

    client.post(url, {**payload, "page_url": page}, headers=XHR)

    feedback = Feedback.objects.get()
    assert feedback.url_name == "library-detail"
    # Canonical Version.slug, the same form the version cookie stores, so
    # URL-driven and cookie-driven versions group together.
    assert feedback.boost_version == "boost-1-88-0"


def test_client_diagnostics_are_captured_but_bounded(client, url, payload):
    """The browser blob is untrusted: oversized entries and junk keys are dropped."""
    blob = json.dumps(
        {
            "viewport": "1440x900",
            "device": "desktop",
            "console_errors": [f"boom {i}" for i in range(50)],
            "search_query": "asio timer",
            "unexpected": {"nested": "junk"},
        }
    )

    client.post(url, {**payload, "diagnostics": blob}, headers=XHR)

    diagnostics = Feedback.objects.get().diagnostics
    assert diagnostics["viewport"] == "1440x900"
    assert diagnostics["search_query"] == "asio timer"
    assert len(diagnostics["console_errors"]) == RING_BUFFER_LIMIT
    assert "unexpected" not in diagnostics


def test_server_errors_are_attached_to_a_later_submission(
    client, url, payload, rf, user
):
    """A 500 page cannot show the widget, so the error must survive until the report."""
    broken = rf.get("/library/1.88.0/beast/")
    broken.user = user
    broken.id = "req-abc123"
    try:
        raise ValueError("no such column: libraries_library.retired")
    except ValueError:
        got_request_exception.send(sender=None, request=broken)

    client.post(url, payload, headers=XHR)

    errors = Feedback.objects.get().diagnostics["server_errors"]
    assert len(errors) == 1
    assert errors[0]["type"] == "ValueError"
    assert "no such column" in errors[0]["message"]
    assert errors[0]["path"] == "/library/1.88.0/beast/"
    assert errors[0]["request_id"] == "req-abc123"


def test_server_errors_are_not_recorded_for_signed_out_visitors(rf):
    """Nothing to attach them to, and no report can follow."""
    request = rf.get("/libraries/")
    request.user = AnonymousUser()
    try:
        raise ValueError("boom")
    except ValueError:
        got_request_exception.send(sender=None, request=request)

    assert recent_server_errors(request.user) == {}


def test_widget_renders_with_a_working_no_js_launcher(rf, user):
    """Rendered through the tag, since no page view supplies its context."""
    request = rf.get("/libraries/")
    request.user = user

    html = Template("{% load feedback_tags %}{% feedback_widget %}").render(
        Context({"request": request, "csrf_token": "a-test-token"})
    )

    assert 'class="feedback-widget"' in html
    # The launcher must be a real link carrying the originating page, or the
    # no-JS path has nowhere to go and loses the page being described.
    assert f'href="{reverse("feedback")}?from=' in html
    assert "a-test-token" in html, "the tag must forward csrf_token into the widget"
    assert 'enctype="multipart/form-data"' in html
    assert 'name="image"' in html


@waffle.testutils.override_flag("v3", active=True)
@waffle.testutils.override_flag("beta_feedback", active=True)
def test_widget_is_suppressed_on_the_standalone_form(client, url):
    """The page is already the form; a launcher on it would open a duplicate."""
    response = client.get(url)

    content = response.content.decode()
    assert 'class="feedback-widget"' not in content
    assert 'class="feedback-page__form"' in content


@pytest.mark.parametrize(
    "extra,headers,expected",
    [
        ({}, XHR, Feedback.Source.WIDGET),
        ({"diagnostics": '{"viewport": "800x600"}'}, {}, Feedback.Source.PAGE),
        ({}, {}, Feedback.Source.PAGE_NO_JS),
    ],
)
def test_source_records_which_form_was_used(
    client, url, payload, extra, headers, expected
):
    """Derived server-side, so triage can see whether the no-JS path is in use."""
    client.post(url, {**payload, **extra}, headers=headers)

    assert Feedback.objects.get().source == expected


def test_admin_changelist_renders_for_triage(client, super_user, url, payload):
    client.post(url, payload, headers=XHR)
    client.force_login(super_user)  # replaces the autouse login

    response = client.get(reverse("admin:feedback_feedback_changelist"))

    assert response.status_code == 200
    assert payload["message"] in response.content.decode()
