import structlog

from django.core.management import call_command
from django.conf import settings

from config.celery import app


logger = structlog.getLogger(__name__)


@app.task
def sync_mailinglist_stats():
    """Task to create EmailData from hyperkitty database."""
    if not settings.HYPERKITTY_DATABASE_NAME:
        logger.warning("HYPERKITTY_DATABASE_NAME not set.")
        return
    call_command("sync_mailinglist_stats")
