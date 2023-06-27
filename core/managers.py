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

    def clear_cache_by_content_type(self, content_type):
        """Clears the static content cache of all rendered content of a given type."""
        cache = caches["static_content"]
        results = self.filter(content_type=content_type)
        for result in results:
            cache.delete(result.cache_key)

        logger.info(
            "rendered_content_manager_clear_cache_by_content_type",
            cache_name="static_content",
            content_type=content_type,
            count=len(results),
        )
