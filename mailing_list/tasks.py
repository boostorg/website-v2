import datetime

import structlog

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from config.celery import app
from mailing_list import constants
from mailing_list.client import MailmanAPIError, MailmanClient
from mailing_list.mixins import verified_emails_for_user
from mailing_list.models import SubscriptionStatus, UserMailingListSubscription

logger = structlog.getLogger(__name__)


@app.task
def sync_mailinglist_stats():
    """Task to create EmailData from hyperkitty database."""
    if not settings.HYPERKITTY_DATABASE_NAME:
        logger.warning("HYPERKITTY_DATABASE_NAME not set.")
        return
    call_command("sync_mailinglist_stats")


@app.task
def sync_mailman_membership_for_user(user_id):
    """Pull a user's real Mailman membership into local subscription state.

    Someone can subscribe directly through Postorious, bypassing this site
    entirely - our local UserMailingListSubscription table then has no record
    of it, so the "manage your lists" modal shows that list as unchecked even
    though the user is already on it. This is fired (async, off the request
    path) on login to reconcile the two: for each of the user's verified
    emails, any managed list Mailman already shows them confirmed on gets a
    local ACTIVE record if one doesn't already exist.

    Deliberately does not touch lists Mailman does *not* show them on - a
    missing local record with no Mailman membership just means "never
    subscribed", not something to unsubscribe or otherwise change.
    """
    User = get_user_model()
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return

    emails = verified_emails_for_user(user)
    if not emails:
        return

    managed_lists = constants.MAILMAN_LISTS
    already_active = set(
        UserMailingListSubscription.objects.filter(
            user=user, list_id__in=managed_lists, status=SubscriptionStatus.ACTIVE
        ).values_list("list_id", flat=True)
    )

    client = MailmanClient()
    for list_id in managed_lists:
        if list_id in already_active:
            continue
        for email in emails:
            try:
                confirmed = client.is_confirmed(email, list_id)
            except MailmanAPIError as exc:
                logger.error(
                    "mailman_membership_sync_error",
                    list_id=list_id,
                    error=str(exc),
                )
                continue
            if not confirmed:
                continue
            try:
                with transaction.atomic():
                    UserMailingListSubscription.objects.update_or_create(
                        user=user,
                        list_id=list_id,
                        defaults={"email": email, "status": SubscriptionStatus.ACTIVE},
                    )
            except IntegrityError:
                # (list_id, email) already claimed by another account - leave it,
                # this sync must never reassign someone else's subscription.
                pass
            break


@app.task
def purge_expired_pending_subscriptions():
    """Delete pending subscription records older than the 7-day confirmation window."""
    cutoff = timezone.now() - datetime.timedelta(days=7)
    deleted, _ = UserMailingListSubscription.objects.filter(
        status=SubscriptionStatus.PENDING,
        subscribed_at__lt=cutoff,
    ).delete()
    if deleted:
        logger.info("purged_pending_subscriptions", count=deleted)
