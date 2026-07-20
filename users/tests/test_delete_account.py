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
        user.delete_account()

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
def test_delete_account_unsubscribes_and_removes_mailing_lists(
    user, django_capture_on_commit_callbacks
):
    """Active external subscriptions are unsubscribed; all local rows dropped."""
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
        # Only the ACTIVE subscription hits the external unsubscribe API.
        MockClient.return_value.unsubscribe.assert_called_once_with(
            "active@example.com", "dev.boost.org"
        )

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
def test_v3_delete_invalid_confirmation_reopens_modal(user, tp):
    with tp.login(user):
        res = tp.post("profile-delete", data={"verify": "wrong"})

    user.refresh_from_db()
    assert user.delete_permanently_at is None
    assert res.status_code == 302
    assert "#delete-account-dialog" in res.url


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
def test_v3_delete_immediately_anonymizes_and_logs_out(
    user, tp, django_capture_on_commit_callbacks
):
    user.delete_permanently_at = timezone.now() + datetime.timedelta(days=10)
    user.save()

    with tp.login(user):
        with django_capture_on_commit_callbacks(execute=True):
            res = tp.post(
                "profile-delete-immediately", data={"verify": "delete my account"}
            )

    user.refresh_from_db()
    assert user.is_active is False
    assert user.email.startswith("deleted-")
    assert res.status_code == 302
