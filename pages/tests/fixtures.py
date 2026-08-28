import pytest

from django.utils.timezone import now
from wagtail.models import Collection
from wagtail.models import Locale
from wagtail.models import Page
from wagtail.models import Site
from wagtail.search.index import insert_or_update_object

from pages.mixins import ContentTag
from pages.models import PostIndexPage
from pages.models import PostPage
from pages.models import RoutableHomePage


@pytest.fixture
def wagtail_home(db):
    """Minimal page tree.

    pytest runs with --no-migrations, so Wagtail's initial data (the root page,
    the default collection and the default site) is never created for us.
    """
    Locale.objects.get_or_create(language_code="en")
    if not Collection.get_first_root_node():
        Collection.add_root(name="Root")
    root = Page.add_root(instance=Page(title="Root", slug="root"))
    return root.add_child(instance=RoutableHomePage(title="Home", slug="home"))


@pytest.fixture
def post_index_page(wagtail_home):
    return wagtail_home.add_child(instance=PostIndexPage(title="Posts", slug="posts"))


@pytest.fixture
def wagtail_site(wagtail_home):
    """Default site, without which page.url returns None and nothing is servable."""
    site = Site.objects.create(
        hostname="testserver",
        port=80,
        root_page=wagtail_home,
        is_default_site=True,
    )
    yield site
    # Wagtail caches site root paths in the shared (Redis) cache, so without
    # this the test site outlives the test run and every page URL in the dev
    # environment resolves to None until the cache is flushed.
    Site.clear_site_root_paths_cache()


def _resolve_tags(tags):
    """Accept "beast" or ("beast", "Beast") and return ContentTag instances."""
    resolved = []
    for tag in tags:
        slug, name = tag if isinstance(tag, tuple) else (tag, tag.title())
        content_tag, _ = ContentTag.objects.get_or_create(
            slug=slug, defaults={"name": name}
        )
        resolved.append(content_tag)
    return resolved


@pytest.fixture
def make_post_page(post_index_page):
    def _make_post_page(
        title="A Post",
        block="news",
        body="Post body",
        owner=None,
        tags=(),
        live=True,
        summary="A summary",
        first_published_at=None,
        **kwargs,
    ):
        page = PostPage(
            title=title,
            content=[(block, body)],
            owner=owner,
            live=live,
            summary=summary,
            first_published_at=first_published_at or now(),
            **kwargs,
        )
        post_index_page.add_child(instance=page)
        if tags:
            page.tags.set(_resolve_tags(tags))
            page.save()

        # Indexing normally happens in a task queued with transaction.on_commit,
        # which never runs under the non-transactional django_db fixture, so
        # every search would silently return nothing. Index the page directly.
        insert_or_update_object(page)
        return page

    return _make_post_page
