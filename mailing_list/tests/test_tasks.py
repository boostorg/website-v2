import datetime

import pytest
from django.utils import timezone
from model_bakery import baker

from libraries.models import CommitAuthor, CommitAuthorEmail
from mailing_list.models import (
    SubscriptionStatus,
    UserMailingListSubscription,
    ListPosting,
    MailingListActivity,
)
from mailing_list.tasks import (
    purge_expired_pending_subscriptions,
    calculate_mailing_list_activity,
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
def test_no_commit_author_activity(user):
    """test that if a user has no commit authors or commit author emails, no mailinglist activity is created"""
    calculate_mailing_list_activity()

    assert MailingListActivity.objects.count() == 0


@pytest.mark.django_db(databases=["default", "hyperkitty"])
def test_one_commit_author_email(user):
    """test that a user with one commit author email successfully counts all posts"""
    test_email = "example@example.com"

    ca = baker.make(CommitAuthor, user=user)
    baker.make(
        CommitAuthorEmail,
        author=ca,
        email=test_email,
    )

    for i in range(1, 6):
        ListPosting.objects.create(
            id=i,
            date=timezone.now(),
            sender_id=test_email,
        )

    calculate_mailing_list_activity()

    assert MailingListActivity.objects.count() == 1
    assert MailingListActivity.objects.get(user=user).count == 5


@pytest.mark.django_db(databases=["default", "hyperkitty"])
def test_two_commit_author_email(user):
    """test that a user with two commit author emails successfully counts all posts"""
    test_email = "example@example.com"
    test_email_2 = "example2@example.com"
    test_email_3 = "example3@example.com"

    ca = baker.make(CommitAuthor, user=user)
    baker.make(
        CommitAuthorEmail,
        author=ca,
        email=test_email,
    )

    ca_2 = baker.make(CommitAuthor, user=user)
    baker.make(
        CommitAuthorEmail,
        author=ca_2,
        email=test_email_2,
    )

    for i in range(1, 6):
        ListPosting.objects.create(
            id=i,
            date=timezone.now(),
            sender_id=test_email,
        )

    for i in range(6, 11):
        ListPosting.objects.create(
            id=i,
            date=timezone.now(),
            sender_id=test_email_2,
        )

    for i in range(11, 16):
        ListPosting.objects.create(
            id=i,
            date=timezone.now(),
            sender_id=test_email_3,
        )

    calculate_mailing_list_activity()

    assert MailingListActivity.objects.count() == 1
    assert MailingListActivity.objects.get(user=user).count == 10
