import structlog

from django.db import models

logger = structlog.get_logger()


class RenderedContentManager(models.Manager):
    def delete_by_content_type(self, content_type):
        self.filter(content_type=content_type).delete()
        logger.info(
            "rendered_content_manager_delete_by_content_type", content_type=content_type
        )
