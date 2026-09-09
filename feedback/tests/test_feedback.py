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
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.signals import got_request_exception
from django.db import transaction
from django.template import Context, Template
from django.test import Client
from django.urls import reverse
from PIL import Image

from feedback.diagnostics import RING_BUFFER_LIMIT
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
def beta_flags():
    """The endpoint 404s unless both flags are on, so every test needs the beta open.

    `WAFFLE_FLAG_DEFAULT` is False, so without this the whole module would 404.
    """
    with (
        waffle.testutils.override_flag("v3", active=True),
        waffle.testutils.override_flag("beta_feedback", active=True),
    ):
        yield


@pytest.fixture(autouse=True)
def signed_in(client, user):
    """Most paths are exercised signed in; the anonymous tests use their own client."""
    client.force_login(user)
    return user


def test_submission_attaches_the_logged_in_user(client, url, payload, user):
    response = client.post(url, payload, headers=XHR)

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    feedback = Feedback.objects.get()
    assert feedback.user == user
    assert feedback.status == Feedback.Status.NEW


@pytest.mark.parametrize("flag", ["v3", "beta_feedback"])
def test_the_endpoint_is_closed_when_the_beta_is_off(client, url, payload, flag):
    """The flag has to switch feedback off, not just hide the launcher."""
    with waffle.testutils.override_flag(flag, active=False):
        assert client.get(url).status_code == 404
        assert client.post(url, payload, headers=XHR).status_code == 404

    assert not Feedback.objects.exists()


def test_a_closed_endpoint_is_not_advertised_to_signed_out_visitors(url):
    """The flag closes the route for everyone, not only for members."""
    with waffle.testutils.override_flag("beta_feedback", active=False):
        assert Client().get(url).status_code == 404


def test_signed_out_submission_is_accepted_without_a_user(url, payload):
    """The pages being reported on are public, so reporting on them is too."""
    response = Client().post(url, payload, headers=XHR)

    assert response.status_code == 200
    assert Feedback.objects.get().user is None


def test_signed_out_visitor_gets_the_standalone_form(url):
    response = Client().get(url)

    content = response.content.decode()
    assert response.status_code == 200
    assert 'class="feedback-page__form"' in content
    assert 'name="contact_email"' in content, "the no-JS form needs the field too"


def test_screenshot_is_stored_with_the_feedback(client, url, payload):
    screenshot = SimpleUploadedFile("shot.png", png_bytes(10), "image/png")

    response = client.post(url, {**payload, "image": screenshot}, headers=XHR)

    assert response.status_code == 200
    assert Feedback.objects.get().image.name.startswith("feedback/")


def test_screenshots_with_the_same_name_do_not_collide(client, url, payload):
    """Media storage overwrites by name, so identical filenames must not share a path."""
    paths = []
    for _ in range(2):
        shot = SimpleUploadedFile("image.png", png_bytes(10), "image/png")
        client.post(url, {**payload, "image": shot}, headers=XHR)
        # By pk, not created_at: two submissions in the same test can share a timestamp.
        paths.append(Feedback.objects.order_by("-pk").first().image.name)

    assert paths[0] != paths[1]
    assert all(p.endswith(".png") for p in paths)


def test_deleting_feedback_removes_its_screenshot(
    client, url, payload, django_capture_on_commit_callbacks
):
    """Admin deletions must not leave the file orphaned in storage."""
    shot = SimpleUploadedFile("shot.png", png_bytes(10), "image/png")
    client.post(url, {**payload, "image": shot}, headers=XHR)
    feedback = Feedback.objects.get()
    name = feedback.image.name
    assert default_storage.exists(name)

    with django_capture_on_commit_callbacks(execute=True):
        feedback.delete()

    assert not default_storage.exists(name)


def test_a_rolled_back_delete_keeps_the_screenshot(client, url, payload):
    """The file removal is deferred to commit — it cannot be undone if it runs early."""
    shot = SimpleUploadedFile("shot.png", png_bytes(10), "image/png")
    client.post(url, {**payload, "image": shot}, headers=XHR)
    feedback = Feedback.objects.get()
    name = feedback.image.name

    with pytest.raises(RuntimeError), transaction.atomic():
        feedback.delete()
        raise RuntimeError("rolled back")

    assert default_storage.exists(name)


def test_oversized_screenshot_is_rejected(client, url, payload):
    content = png_bytes(900)
    assert len(content) >= IMAGE_MAX_BYTES, "fixture must exceed the ceiling"
    screenshot = SimpleUploadedFile("huge.png", content, "image/png")

    response = client.post(url, {**payload, "image": screenshot}, headers=XHR)

    assert response.status_code == 400
    assert "image" in response.json()["errors"]
    assert not Feedback.objects.exists()


@pytest.mark.parametrize(
    "field,invalid",
    [
        ("message", {"message": ""}),
        ("feedback_type", {"feedback_type": ""}),
        ("image", {"image": ("notes.gif", b"GIF89a-not-a-screenshot", "image/gif")}),
    ],
)
def test_invalid_submissions_are_rejected_with_the_message_intact(
    client, url, payload, field, invalid
):
    """Each rejection the ticket names; the member must never lose what they wrote."""
    if field == "image":
        name, content, content_type = invalid["image"]
        invalid = {"image": SimpleUploadedFile(name, content, content_type)}

    response = client.post(url, {**payload, **invalid}, headers=XHR)

    assert response.status_code == 400
    assert field in response.json()["errors"]
    assert not Feedback.objects.exists()


def test_invalid_submissions_do_not_consume_the_rate_limit(
    client, url, payload, monkeypatch
):
    """The quota counts reports, so a member fighting a rejection keeps their budget."""
    monkeypatch.setattr("feedback.views.RATE_LIMIT", 1)

    for _ in range(3):
        client.post(url, {**payload, "message": ""}, headers=XHR)

    response = client.post(url, payload, headers=XHR)

    assert response.status_code == 200
    assert Feedback.objects.count() == 1


def test_the_rate_limit_throttles_further_submissions(
    client, url, payload, monkeypatch
):
    monkeypatch.setattr("feedback.views.RATE_LIMIT", 1)
    assert client.post(url, payload, headers=XHR).status_code == 200

    response = client.post(url, payload, headers=XHR)

    assert response.status_code == 429
    assert Feedback.objects.count() == 1


def test_anonymous_submitters_get_their_own_rate_limit_bucket(
    url, payload, monkeypatch
):
    """Keyed by session, so one visitor's quota cannot throttle every other one.

    Without a session key they would all share the anonymous user's empty pk.
    """
    monkeypatch.setattr("feedback.views.RATE_LIMIT", 1)
    first, second = Client(), Client()

    assert first.post(url, payload, headers=XHR).status_code == 200
    assert first.post(url, payload, headers=XHR).status_code == 429

    assert second.post(url, payload, headers=XHR).status_code == 200
    assert Feedback.objects.count() == 2


def test_an_anonymous_submitter_can_leave_an_email(url, payload):
    """The only way back to a submitter with no account."""
    contact = "reporter@example.com"

    response = Client().post(url, {**payload, "contact_email": contact}, headers=XHR)

    assert response.status_code == 200
    feedback = Feedback.objects.get()
    assert feedback.contact_email == contact
    assert feedback.reply_to == contact


@pytest.mark.parametrize(
    "contact,expected",
    [
        ("reporter@example.com", "Anonymous <reporter@example.com>"),
        ("", "Anonymous"),
    ],
)
def test_an_anonymous_row_names_its_contact_address(contact, expected):
    """Triage reads who to answer off the changelist, without opening the row."""
    assert Feedback(contact_email=contact).submitter == expected


def test_the_email_is_optional_for_anonymous_submitters(url, payload):
    """An address is a nicety; refusing the report without one would lose it."""
    response = Client().post(url, payload, headers=XHR)

    assert response.status_code == 200
    assert Feedback.objects.get().contact_email == ""


def test_an_unusable_email_is_rejected_rather_than_stored(url, payload):
    """A malformed address is worse than none — it looks like a reply is possible."""
    response = Client().post(
        url, {**payload, "contact_email": "not-an-address"}, headers=XHR
    )

    assert response.status_code == 400
    assert "contact_email" in response.json()["errors"]
    assert not Feedback.objects.exists()


def test_a_members_identity_is_used_without_asking_for_an_email(
    client, url, payload, user
):
    """The field is not on a member's form, so a posted value cannot displace their account."""
    response = client.post(
        url, {**payload, "contact_email": "spoofed@example.com"}, headers=XHR
    )

    assert response.status_code == 200
    feedback = Feedback.objects.get()
    assert feedback.contact_email == ""
    assert feedback.reply_to == user.email


def test_a_rejected_no_js_submission_re_renders_the_message(client, url, payload):
    """The standalone form has no client state, so the server must echo it back."""
    response = client.post(url, {**payload, "feedback_type": ""})

    assert response.status_code == 200
    assert payload["message"] in response.content.decode()


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


@pytest.mark.parametrize(
    "page_url",
    [
        "http://testserver/library/latest/beast/",
        # No version anywhere: the page was showing the most recent release.
        "http://testserver/libraries/",
    ],
)
def test_latest_is_pinned_to_the_release_it_meant(
    client, url, payload, version, page_url
):
    """A "latest" URL moves with every release, so it cannot be what a report stores."""
    client.post(url, {**payload, "page_url": page_url}, headers=XHR)

    assert Feedback.objects.get().boost_version == version.slug


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


def test_server_errors_follow_a_signed_out_visitor_by_session(url, payload, rf):
    """A 500 page cannot show the widget, so the error must outlive the request.

    The first report is what gives an anonymous visitor a session to file under.
    """
    anonymous = Client()
    anonymous.post(url, payload, headers=XHR)

    broken = rf.get("/library/1.88.0/beast/")
    broken.user = AnonymousUser()
    broken.session = anonymous.session
    try:
        raise ValueError("no such column: libraries_library.retired")
    except ValueError:
        got_request_exception.send(sender=None, request=broken)

    anonymous.post(url, payload, headers=XHR)

    errors = Feedback.objects.order_by("-pk").first().diagnostics["server_errors"]
    assert len(errors) == 1
    assert errors[0]["type"] == "ValueError"


def test_one_visitors_server_errors_do_not_leak_into_anothers_report(url, payload, rf):
    """Sessions are the boundary; a shared bucket would hand out other people's paths."""
    reporter, bystander = Client(), Client()
    reporter.post(url, payload, headers=XHR)

    broken = rf.get("/libraries/")
    broken.user = AnonymousUser()
    broken.session = reporter.session
    try:
        raise ValueError("boom")
    except ValueError:
        got_request_exception.send(sender=None, request=broken)

    bystander.post(url, payload, headers=XHR)

    assert "server_errors" not in Feedback.objects.order_by("-pk").first().diagnostics


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


def test_the_email_field_is_offered_only_to_signed_out_visitors(rf, user):
    """Asking a member for an address we already hold is noise on the form."""
    request = rf.get("/libraries/")

    def widget_html(as_user):
        request.user = as_user
        return Template("{% load feedback_tags %}{% feedback_widget %}").render(
            Context({"request": request, "csrf_token": "a-test-token"})
        )

    assert 'name="contact_email"' in widget_html(AnonymousUser())
    assert 'name="contact_email"' not in widget_html(user)


def test_widget_renders_for_a_signed_out_visitor(rf):
    """The launcher is site-wide now, so it must render without an account."""
    request = rf.get("/libraries/")
    request.user = AnonymousUser()

    html = Template("{% load feedback_tags %}{% feedback_widget %}").render(
        Context({"request": request, "csrf_token": "a-test-token"})
    )

    assert 'class="feedback-widget"' in html


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
