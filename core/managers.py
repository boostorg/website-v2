import structlog

from django.core.cache import caches
from django.db import models

logger = structlog.get_logger()


class RenderedContentManager(models.Manager):
    def delete_by_content_type(self, content_type):
        """Deletes all rendered content of a given type."""
        self.filter(content_type=content_type).delete()
        logger.info(
            "rendered_content_manager_delete_by_content_type", content_type=content_type
        )