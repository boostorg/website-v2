import datetime
from unittest.mock import patch

import pytest
from django.utils import timezone
from model_bakery import baker

from mailing_list.constants import MAILMAN_LISTS
from mailing_list.models import SubscriptionStatus, UserMailingListSubscription
from mailing_list.tasks import (
    purge_expired_pending_subscriptions,
    sync_mailman_membership_for_user,
)


@pytest.fixture
def user(db):
    return baker.make("users.User")


@pytest.mark.django_db
def test_purge_deletes_expired_pending(user):
    """purge_expired_pending_subscriptions: removes PENDING subscriptions older than 7 days."""
    old_sub = baker.make(
        UserMailingListSubscription,
        user=user,
        list_id="boost.lists.boost.org",
        status=SubscriptionStatus.PENDING,
    )
    UserMailingListSubscription.objects.filter(pk=old_sub.pk).update(
        subscribed_at=timezone.now() - datetime.timedelta(days=8)
    )

    purge_expired_pending_subscriptions()

    assert not UserMailingListSubscription.objects.filter(pk=old_sub.pk).exists()


@pytest.mark.django_db
def test_purge_keeps_recent_pending(user):
    """purge_expired_pending_subscriptions: retains PENDING subscriptions created within the last 7 days."""
    recent_sub = baker.make(
        UserMailingListSubscription,
        user=user,
        list_id="boost.lists.boost.org",
        status=SubscriptionStatus.PENDING,
    )

    purge_expired_pending_subscriptions()

    assert UserMailingListSubscription.objects.filter(pk=recent_sub.pk).exists()


@pytest.mark.django_db
def test_purge_keeps_active_records(user):
    """purge_expired_pending_subscriptions: does not touch ACTIVE subscriptions regardless of age."""
    active_sub = baker.make(
        UserMailingListSubscription,
        user=user,
        list_id="boost.lists.boost.org",
        status=SubscriptionStatus.ACTIVE,
    )
    UserMailingListSubscription.objects.filter(pk=active_sub.pk).update(
        subscribed_at=timezone.now() - datetime.timedelta(days=30)
    )

    purge_expired_pending_subscriptions()

    assert UserMailingListSubscription.objects.filter(pk=active_sub.pk).exists()


@pytest.mark.django_db
def test_sync_creates_active_record_for_confirmed_external_membership(user):
    """sync_mailman_membership_for_user: a list Mailman shows the user's account
    email confirmed on, that we have no local record of, gets one created -
    covering a subscription made directly through Postorious."""
    with patch("mailing_list.tasks.MailmanClient") as MockClient:
        MockClient.return_value.is_confirmed.return_value = True
        sync_mailman_membership_for_user(user.pk)

    sub = UserMailingListSubscription.objects.get(user=user, list_id=MAILMAN_LISTS[0])
    assert sub.status == SubscriptionStatus.ACTIVE
    assert sub.email == user.email


@pytest.mark.django_db
def test_sync_does_not_touch_lists_user_is_not_confirmed_on(user):
    """sync_mailman_membership_for_user: no local record is created for a list
    Mailman doesn't show the user confirmed on."""
    with patch("mailing_list.tasks.MailmanClient") as MockClient:
        MockClient.return_value.is_confirmed.return_value = False
        sync_mailman_membership_for_user(user.pk)

    assert not UserMailingListSubscription.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_sync_skips_lists_already_tracked_active_locally(user):
    """sync_mailman_membership_for_user: doesn't re-query or overwrite a list
    already tracked ACTIVE locally."""
    baker.make(
        UserMailingListSubscription,
        user=user,
        list_id=MAILMAN_LISTS[0],
        email=user.email,
        status=SubscriptionStatus.ACTIVE,
    )
    with patch("mailing_list.tasks.MailmanClient") as MockClient:
        sync_mailman_membership_for_user(user.pk)

    calls = [c.args for c in MockClient.return_value.is_confirmed.call_args_list]
    assert (user.email, MAILMAN_LISTS[0]) not in calls


@pytest.mark.django_db
def test_sync_no_op_for_user_with_no_verified_emails(db):
    """sync_mailman_membership_for_user: a user with no account email and no
    verified commit emails makes no Mailman calls at all."""
    user = baker.make("users.User", email="")
    with patch("mailing_list.tasks.MailmanClient") as MockClient:
        sync_mailman_membership_for_user(user.pk)

    MockClient.return_value.is_confirmed.assert_not_called()


@pytest.mark.django_db
def test_sync_uses_verified_commit_email_not_just_account_email(user):
    """sync_mailman_membership_for_user: also checks a verified commit-author
    email, and records the subscription under that email."""
    commit_email = "commits@example.com"
    baker.make(
        "libraries.CommitAuthorEmail",
        claimed_by=user,
        claim_verified=True,
        email=commit_email,
    )

    def fake_is_confirmed(email, list_id):
        return email == commit_email

    with patch("mailing_list.tasks.MailmanClient") as MockClient:
        MockClient.return_value.is_confirmed.side_effect = fake_is_confirmed
        sync_mailman_membership_for_user(user.pk)

    sub = UserMailingListSubscription.objects.get(user=user, list_id=MAILMAN_LISTS[0])
    assert sub.email == commit_email
    assert sub.status == SubscriptionStatus.ACTIVE


@pytest.mark.django_db
def test_sync_unknown_user_is_a_no_op(db):
    """sync_mailman_membership_for_user: a stale/deleted user id doesn't raise."""
    with patch("mailing_list.tasks.MailmanClient") as MockClient:
        sync_mailman_membership_for_user(999999999)

    MockClient.return_value.is_confirmed.assert_not_called()
