import structlog

from django.core.cache import caches
from django.db import models

from django.utils import timezone
import datetime
from django.conf import settings

logger = structlog.get_logger()


class RenderedContentManager(models.Manager):
    def clear_cache_by_cache_type_and_date(
        self,
        cache_type="static_content_",
        older_than_days=settings.CLEAR_STATIC_CONTENT_CACHE_DAYS,
    ):
        older_than = timezone.now() - datetime.timedelta(days=older_than_days)
        deleted_count, _ = self.filter(
            cache_key__startswith=cache_type, created__lte=older_than
        ).delete()
        logger.info(
            "rendered_content_manager_clear_cache_by_cache_type_and_date",
            cache_type=cache_type,
            count=deleted_count,
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

    def delete_by_cache_key(self, cache_key):
        """Deletes a rendered content object by its cache key."""
        self.filter(cache_key=cache_key).delete()
        logger.info("rendered_content_manager_delete_by_cache_key", cache_key=cache_key)

    def delete_by_content_type(self, content_type):
        """Deletes all rendered content of a given type."""
        self.filter(content_type=content_type).delete()
        logger.info(
            "rendered_content_manager_delete_by_content_type", content_type=content_type
        )


class PopularSearchTermManager(models.Manager):
    def visible(self):
        """Rows safe to display on the homepage, pinned first then by rank.

        Filters out `PopularSearchTermExclusion` labels (case-insensitive) so
        admin exclusions take effect without re-running the refresh task.
        """
        from django.db.models.functions import Lower
        from core.models import PopularSearchTermExclusion

        excluded_lower = list(
            PopularSearchTermExclusion.objects.annotate(t=Lower("term")).values_list(
                "t", flat=True
            )
        )
        return (
            self.annotate(label_lower=Lower("label"))
            .exclude(label_lower__in=excluded_lower)
            .order_by("-is_pinned", "rank")
        )
