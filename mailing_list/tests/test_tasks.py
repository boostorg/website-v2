import datetime

import pytest
from django.utils import timezone
from model_bakery import baker

from mailing_list.models import SubscriptionStatus, UserMailingListSubscription
from mailing_list.tasks import purge_expired_pending_subscriptions


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
