from datetime import timedelta

import structlog
from celery import shared_task
from django.utils import timezone

from .constants import ASCIIDOCTOR_SANDBOX_DOCUMENT_RETENTION_DAYS
from .models import SandboxDocument

logger = structlog.get_logger(__name__)


@shared_task
def cleanup_old_sandbox_documents():
    """
    Delete sandbox documents last updated before the configured retention period.
    """
    cutoff_date = timezone.now() - timedelta(
        days=ASCIIDOCTOR_SANDBOX_DOCUMENT_RETENTION_DAYS
    )

    old_documents = SandboxDocument.objects.filter(updated_at__lt=cutoff_date)
    count = old_documents.count()

    if count == 0:
        logger.info("No old sandbox documents to clean up")
        return

    logger.info(
        f"Deleting {count} sandbox documents older than "
        f"{ASCIIDOCTOR_SANDBOX_DOCUMENT_RETENTION_DAYS} days"
    )

    deleted_count = 0
    for document in old_documents:
        logger.debug(f"Deleting sandbox document {document.id=}")
        document.delete()
        deleted_count += 1

    logger.info(f"Successfully deleted {deleted_count} old sandbox documents")
