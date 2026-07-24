import datetime
from unittest.mock import patch

import pytest
import waffle.testutils
from model_bakery import baker

from django.contrib.auth import get_user_model
from django.utils import timezone

from mailing_list.models import SubscriptionStatus, UserMailingListSubscription
from ..models import LastSeen, Preferences

User = get_user_model()


@pytest.mark.django_db
def test_delete_account_scrubs_pii_and_identity(
    user, django_capture_on_commit_callbacks
):
    """delete_account anonymizes the row in place and clears public PII."""
    user.github_username = "octocat"
    user.profile_links = {
        "github": "https://github.com/octocat",
        "email": "octo@example.com",
    }
    user.indicate_last_login_method = True
    user.image_uploaded = True
    user.save()
    user.badges.add(baker.make("users.Badge"))

    original_email = user.email
    original_id = user.id

    with django_capture_on_commit_callbacks(execute=True):
        user.delete_account(extended_scrub=True)

    user.refresh_from_db()
    # The row is preserved (authored content stays attributed to it).
    assert user.id == original_id
    assert user.is_active is False
    assert user.has_usable_password() is False
    assert user.display_name == "John Doe"
    assert user.first_name == "John"
    assert user.last_name == "Doe"
    assert user.email != original_email
    assert user.email.startswith("deleted-")
    # Extra fields scrubbed.
    assert user.github_username == ""
    assert user.profile_links == {}
    assert user.indicate_last_login_method is False
    assert user.image_uploaded is False
    assert not user.profile_image
    assert user.badges.count() == 0
    assert user.delete_permanently_at is None


@pytest.mark.django_db
def test_delete_account_removes_linked_records(
    user, django_capture_on_commit_callbacks
):
    """Preferences and LastSeen are removed on deletion."""
    assert Preferences.objects.filter(user=user).exists()
    assert LastSeen.objects.filter(user=user).exists()

    with django_capture_on_commit_callbacks(execute=True):
        user.delete_account()

    assert not Preferences.objects.filter(user=user).exists()
    assert not LastSeen.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_delete_account_deletes_mailing_list_rows_without_api_call(
    user, django_capture_on_commit_callbacks
):
    """Local subscription rows are deleted (PII removed); Mailman is not called.

    List membership is left to Postorius - we only drop our stored rows.
    """
    baker.make(
        UserMailingListSubscription,
        user=user,
        list_id="dev.boost.org",
        email="active@example.com",
        status=SubscriptionStatus.ACTIVE,
    )
    baker.make(
        UserMailingListSubscription,
        user=user,
        list_id="users.boost.org",
        email="pending@example.com",
        status=SubscriptionStatus.PENDING,
    )

    with patch("mailing_list.client.MailmanClient") as MockClient:
        with django_capture_on_commit_callbacks(execute=True):
            user.delete_account()
        MockClient.assert_not_called()

    assert not UserMailingListSubscription.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_delete_account_is_idempotent(user, django_capture_on_commit_callbacks):
    """A second run (e.g. immediate delete racing the scheduled task) is a no-op."""
    with django_capture_on_commit_callbacks(execute=True):
        user.delete_account()
    with django_capture_on_commit_callbacks(execute=True):
        user.delete_account()  # must not raise

    user.refresh_from_db()
    assert user.is_active is False


@pytest.mark.django_db
@waffle.testutils.override_flag("v3", active=True)
def test_v3_delete_schedules_and_redirects_to_edit(user, tp):
    with tp.login(user):
        res = tp.post("profile-delete", data={"verify": "delete my account"})

    user.refresh_from_db()
    assert user.delete_permanently_at is not None
    assert res.status_code == 302
    assert "edit=true" in res.url


@pytest.mark.django_db
@waffle.testutils.override_flag("v3", active=True)
def test_v3_delete_sends_scheduled_email(user, tp, settings, mailoutbox):
    user.first_name = "Vinnie"
    user.save()

    with tp.login(user):
        tp.post("profile-delete", data={"verify": "delete my account"})

    assert len(mailoutbox) == 1
    email = mailoutbox[0]
    assert email.subject == "Your account is scheduled for deletion"
    assert email.to == [user.email]
    grace = settings.ACCOUNT_DELETION_GRACE_PERIOD_DAYS
    assert f"deletion in {grace} day" in email.body
    assert "Vinnie" in email.body
    # HTML alternative is attached and links out to Postorius.
    html_body, mimetype = email.alternatives[0]
    assert mimetype == "text/html"
    assert "Postorius" in html_body


@pytest.mark.django_db
def test_legacy_delete_does_not_send_scheduled_email(user, tp, mailoutbox):
    """The scheduling email is a V3-only addition; legacy behaviour is unchanged."""
    with tp.login(user):
        tp.post("profile-delete", data={"verify": "delete my account"})

    user.refresh_from_db()
    assert user.delete_permanently_at is not None
    assert not any(
        m.subject == "Your account is scheduled for deletion" for m in mailoutbox
    )


@pytest.mark.django_db
@waffle.testutils.override_flag("v3", active=True)
def test_v3_delete_invalid_confirmation_reopens_modal(user, tp):
    with tp.login(user):
        res = tp.post("profile-delete", data={"verify": "wrong"})

    user.refresh_from_db()
    assert user.delete_permanently_at is None
    assert res.status_code == 302
    assert "#delete-account-dialog" in res.url
    assert "delete_error=1" in res.url


@pytest.mark.django_db
@waffle.testutils.override_flag("v3", active=True)
def test_v3_delete_invalid_confirmation_renders_inline_error(user, tp):
    """The error is shown inline in the modal, not as a global message banner."""
    with tp.login(user):
        tp.post("profile-delete", data={"verify": "wrong"})
        res = tp.get("profile-account", data={"edit": "true", "delete_error": "1"})

    html = res.content.decode()
    # Inline field error rendered inside the modal (quotes are HTML-escaped).
    assert "Please enter" in html
    assert "field--error" in html
    assert 'class="field__error"' in html
    # No message was queued for the global (legacy) banner.
    assert list(res.context["messages"]) == []


@pytest.mark.django_db
@waffle.testutils.override_flag("v3", active=True)
def test_v3_cancel_deletion_clears_schedule(user, tp):
    user.delete_permanently_at = timezone.now() + datetime.timedelta(days=10)
    user.save()

    with tp.login(user):
        res = tp.post("profile-cancel-delete", data={})

    user.refresh_from_db()
    assert user.delete_permanently_at is None
    assert res.status_code == 302
    assert "edit=true" in res.url


@pytest.mark.django_db
@waffle.testutils.override_flag("v3", active=True)
def test_v3_cancel_deletion_shows_no_success_banner(user, tp):
    """V3 relies on the edit-page state, so no legacy success banner is added."""
    user.delete_permanently_at = timezone.now() + datetime.timedelta(days=10)
    user.save()

    with tp.login(user):
        res = tp.post("profile-cancel-delete", data={}, follow=True)

    banners = [str(m) for m in res.context["messages"]]
    assert "Your account is no longer scheduled for deletion." not in banners


@pytest.mark.django_db
def test_legacy_cancel_deletion_keeps_success_banner(user, tp):
    """Legacy behaviour is unchanged: the success banner still fires."""
    user.delete_permanently_at = timezone.now() + datetime.timedelta(days=10)
    user.save()

    with tp.login(user):
        res = tp.post("profile-cancel-delete", data={}, follow=True)

    banners = [str(m) for m in res.context["messages"]]
    assert "Your account is no longer scheduled for deletion." in banners
