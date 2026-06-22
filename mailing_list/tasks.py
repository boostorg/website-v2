import datetime

import structlog

from django.core.management import call_command
from django.conf import settings
from django.utils import timezone

from config.celery import app
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
def purge_expired_pending_subscriptions():
    """Delete pending subscription records older than the 7-day confirmation window."""
    cutoff = timezone.now() - datetime.timedelta(days=7)
    deleted, _ = UserMailingListSubscription.objects.filter(
        status=SubscriptionStatus.PENDING,
        subscribed_at__lt=cutoff,
    ).delete()
    if deleted:
        logger.info("purged_pending_subscriptions", count=deleted)
