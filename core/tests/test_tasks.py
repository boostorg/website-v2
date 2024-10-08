from model_bakery import baker

from django.core.cache import caches
from django.test import override_settings

from core.models import RenderedContent
from core.tasks import (
    clear_rendered_content_cache_by_cache_key,
    clear_rendered_content_cache_by_content_type,
)


TEST_CACHES = {
    "static_content": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "third-unique-snowflake",
        "TIMEOUT": "60",  # Cache timeout in seconds: 1 minute
    },
}


@override_settings(CACHES=TEST_CACHES)
def test_clear_rendered_content_by_content_type():
    baker.make("core.RenderedContent", content_type="keep", cache_key="keep")
    baker.make("core.RenderedContent", content_type="clear", cache_key="clear")

    cache = caches["static_content"]
    cache.set("keep", "keep")
    cache.set("clear", "clear")

    assert cache.get("keep") == "keep"
    assert cache.get("clear") == "clear"

    clear_rendered_content_cache_by_content_type("clear")

    assert cache.get("keep") == "keep"
    assert cache.get("clear") is None

    assert RenderedContent.objects.filter(content_type="keep").exists()
    assert not RenderedContent.objects.filter(content_type="clear").exists()


@override_settings(CACHES=TEST_CACHES)
def test_clear_rendered_content_by_cache_key():
    obj = baker.make("core.RenderedContent", cache_key="clear")
    cache_key = obj.cache_key
    cache = caches["static_content"]
    cache.set(cache_key, "sample content")
    assert cache.get(cache_key) == "sample content"

    clear_rendered_content_cache_by_cache_key(cache_key)
    assert not cache.get(cache_key)
    assert not RenderedContent.objects.filter(cache_key=cache_key).exists()
