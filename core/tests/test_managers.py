from model_bakery import baker

from django.core.cache import caches
from django.test import override_settings

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
