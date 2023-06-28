import structlog

from celery import shared_task
from dateutil.parser import parse

from django.core.cache import caches

from .asciidoc import convert_adoc_to_html, process_adoc_to_html_content
from .boostrenderer import get_content_from_s3
from .models import RenderedContent

logger = structlog.get_logger()


@shared_task
def adoc_to_html(file_path, delete_file=True):
    return convert_adoc_to_html(file_path, delete_file=delete_file)


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
def refresh_content_from_s3(s3_key, cache_key):
    """Calls S3 with the s3_key, then saves the result to the
    RenderedContent object with the given cache_key."""
    content_dict = get_content_from_s3(key=s3_key)
    content = content_dict.get("content")
    if content_dict and content:
        content_type = content_dict.get("content_type")
        if content_type == "text/asciidoc":
            content = process_adoc_to_html_content(content)
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
    defaults = {
        "content_type": content_type,
        "content_html": content_html,
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
    return obj
