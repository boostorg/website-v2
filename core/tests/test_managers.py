import datetime
from model_bakery import baker

from django.conf import settings
from django.core.cache import caches
from django.test import override_settings
from django.utils import timezone

from ..models import RenderedContent


TEST_CACHES = {
    "static_content": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "third-unique-snowflake",
        "TIMEOUT": "60",  # Cache timeout in seconds: 1 minute
    },
}


def test_rendered_content_manager_delete_by_content_type():
    baker.make("core.RenderedContent", content_type="keep")
    baker.make("core.RenderedContent", content_type="clear")

    assert RenderedContent.objects.filter(content_type="keep").exists()
    assert RenderedContent.objects.filter(content_type="clear").exists()

    RenderedContent.objects.delete_by_content_type("clear")

    assert RenderedContent.objects.filter(content_type="keep").exists()
    assert not RenderedContent.objects.filter(content_type="clear").exists()


@override_settings(CACHES=TEST_CACHES)
def test_rendered_content_manager_clear_cache_by_content_type():
    baker.make("core.RenderedContent", content_type="keep", cache_key="keep")
    baker.make("core.RenderedContent", content_type="clear", cache_key="clear")

    cache = caches["static_content"]
    cache.set("keep", "keep")
    cache.set("clear", "clear")

    assert cache.get("keep") == "keep"
    assert cache.get("clear") == "clear"

    RenderedContent.objects.clear_cache_by_content_type("clear")

    assert cache.get("keep") == "keep"
    assert cache.get("clear") is None


def test_delete_by_cache_key():
    baker.make("core.RenderedContent", cache_key="keep")
    baker.make("core.RenderedContent", cache_key="clear")

    assert RenderedContent.objects.filter(cache_key="keep").exists()
    assert RenderedContent.objects.filter(cache_key="clear").exists()

    RenderedContent.objects.delete_by_cache_key("clear")

    assert RenderedContent.objects.filter(cache_key="keep").exists()
    assert not RenderedContent.objects.filter(cache_key="clear").exists()


def test_clear_cache_by_cache_type_and_date(rendered_content):
    cache_type = "cache-key"
    older_than_days = settings.CLEAR_STATIC_CONTENT_CACHE_DAYS

    # Create old cache entry
    old_date = timezone.now() - datetime.timedelta(days=older_than_days + 1)
    old_content = baker.make("core.RenderedContent", cache_key=f"{cache_type}_old")
    old_content.created = old_date
    old_content.save()

    initial_count = RenderedContent.objects.count()
    RenderedContent.objects.clear_cache_by_cache_type_and_date(cache_type=cache_type)
    final_count = RenderedContent.objects.count()
    assert final_count == initial_count - 1
    assert not RenderedContent.objects.filter(cache_key=f"{cache_type}_old").exists()
    assert RenderedContent.objects.filter(cache_key=rendered_content.cache_key).exists()
