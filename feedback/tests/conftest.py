import pytest


@pytest.fixture(autouse=True)
def locmem_cache(settings):
    """The rate limit lives in the cache, so isolate it from Redis and from other tests."""
    settings.CACHES = {
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
    }
    yield
    from django.core.cache import cache

    cache.clear()


@pytest.fixture(autouse=True)
def isolate_media(settings, tmp_path):
    """Keep uploaded screenshots out of the real MEDIA_ROOT."""
    settings.MEDIA_ROOT = tmp_path
