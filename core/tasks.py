import structlog

from celery import shared_task
from dateutil.parser import parse

from django.core.cache import caches

from core.asciidoc import convert_adoc_to_html
from libraries.path_matcher.utils import get_path_match_from_chain
from versions.models import Version
from .boostrenderer import get_content_from_s3
from .constants import RENDERED_CONTENT_BATCH_DELETE_SIZE
from .models import RenderedContent, LatestPathMatchIndicator

logger = structlog.get_logger()


@shared_task
def clear_rendered_content_cache_by_cache_key(cache_key):
    """Deletes a RenderedContent object by its cache key from redis and
    database."""
    cache = caches["static_content"]
    cache.delete(cache_key)
    RenderedContent.objects.delete_by_cache_key(cache_key)


@shared_task
def clear_rendered_content_cache_by_content_type(content_type):
    """Deletes all RenderedContent objects for a given content type from redis
    and database."""
    RenderedContent.objects.clear_cache_by_content_type(content_type)
    RenderedContent.objects.delete_by_content_type(content_type)


@shared_task
def clear_static_content_cache():
    """Runs the manager method to clear the static content cache"""
    RenderedContent.objects.clear_cache_by_cache_type_and_date(
        cache_type="static_content_"
    )


@shared_task
def refresh_content_from_s3(s3_key, cache_key):
    """Calls S3 with the s3_key, then saves the result to the
    RenderedContent object with the given cache_key."""
    content_dict = get_content_from_s3(key=s3_key)

    content = content_dict.get("content")
    if content_dict and content:
        content_type = content_dict.get("content_type")
        if content_type == "text/asciidoc":
            content = convert_adoc_to_html(content)
        last_updated_at_raw = content_dict.get("last_updated_at")
        last_updated_at = parse(last_updated_at_raw) if last_updated_at_raw else None
        # Clear the cache because we're going to update it.
        clear_rendered_content_cache_by_cache_key(cache_key)

        # Update the rendered content.
        save_rendered_content(
            cache_key, content_type, content, last_updated_at=last_updated_at
        )
        # Cache the refreshed rendered content
        cache = caches["static_content"]
        cache.set(cache_key, {"content": content, "content_type": content_type})


@shared_task
def save_rendered_content(cache_key, content_type, content_html, last_updated_at=None):
    """Saves a RenderedContent object to database."""

    match_result = get_path_match_from_chain(
        cache_key.replace("static_content_", ""), Version.objects.most_recent()
    )

    indicator = (
        LatestPathMatchIndicator.DIRECT_MATCH
        if match_result.is_direct_equivalent
        else LatestPathMatchIndicator.CUSTOM_MATCH
    )

    # we don't set the latest_docs_path if it's a direct match, for db size reduction
    defaults = {
        "content_type": content_type,
        "content_html": content_html,
        "latest_path_matched_indicator": indicator,
        "latest_docs_path": (
            match_result.latest_path if not match_result.is_direct_equivalent else None
        ),
        "latest_path_match_class": match_result.matcher,
    }

    if last_updated_at:
        defaults["last_updated_at"] = last_updated_at

    obj, created = RenderedContent.objects.update_or_create(
        cache_key=cache_key[:255], defaults=defaults
    )
    logger.info(
        "content_saved_to_rendered_content",
        cache_key=cache_key,
        content_type=content_type,
        status_code=200,
        obj_id=obj.id,
        obj_created=created,
    )


@shared_task
def delete_all_rendered_content():
    """
    Deletes all RenderedContent objects, in batches to avoid locking the entire table.
    """
    from django.db import connection

    deleted_count = 0

    while True:
        pks = RenderedContent.objects.values_list("pk", flat=True)[
            :RENDERED_CONTENT_BATCH_DELETE_SIZE
        ]
        if not pks:
            break
        batch_size, _ = RenderedContent.objects.filter(pk__in=pks).delete()

        deleted_count += batch_size
        logger.info(f"batch deleted {batch_size=} {deleted_count=}")

    # Reset auto-increment sequence to 1
    with connection.cursor() as cursor:
        cursor.execute(
            f"ALTER SEQUENCE {RenderedContent._meta.db_table}_id_seq RESTART WITH 1"
        )

    logger.info("all_rendered_content_deleted", total_count=deleted_count)
    return deleted_count
