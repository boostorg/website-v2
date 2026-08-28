"""Posts must follow the `v3` flag everywhere they are linked or listed.

With the flag on, every post reference on the site points at the Wagtail post
tree under `/news/`. With it off, every reference goes back to the legacy
`news.Entry` routes under `/news/entry/`, which is what makes the flag a
working rollback switch.
"""

import pytest
from django.urls import reverse
from waffle.testutils import override_flag
from wagtail.models import Collection, Locale, Page, Site

from core.context_processors import header_context
from pages.routing import post_detail_url, post_index_url
from news.services import get_latest_post_cards
from pages.models import PostIndexPage, PostPage, RoutableHomePage


@pytest.fixture
def post_index_page(db):
    Locale.objects.get_or_create(language_code="en")
    if not Collection.get_first_root_node():
        Collection.add_root(name="Root")
    root = Page.get_first_root_node() or Page.add_root(
        instance=Page(title="Root", slug="root")
    )
    home = root.add_child(instance=RoutableHomePage(title="Home", slug="home"))
    Site.objects.all().delete()
    Site.objects.create(hostname="testserver", root_page=home, is_default_site=True)
    return home.add_child(instance=PostIndexPage(title="Posts", slug="news"))


@pytest.fixture
def make_post_page(post_index_page, make_entry):
    def _make_it(entry=None, **kwargs):
        kwargs.setdefault("slug", "a-post")
        entry = entry or make_entry(model_class="News", **kwargs)
        page = PostPage(
            title=entry.title,
            slug=entry.slug,
            owner=entry.author,
            live=entry.is_published,
            first_published_at=entry.publish_at,
            last_published_at=entry.publish_at,
            content=[{"type": "news", "value": entry.content or "body"}],
        )
        post_index_page.add_child(instance=page)
        return entry, page

    return _make_it


class TestPostIndexUrl:
    @override_flag("v3", active=False)
    def test_falls_back_to_legacy_list(self, rf, post_index_page):
        assert post_index_url(rf.get("/")) == reverse("news")

    @override_flag("v3", active=True)
    def test_points_at_wagtail_index(self, rf, post_index_page):
        assert post_index_url(rf.get("/")) == "/news/"

    @override_flag("v3", active=True)
    def test_carries_the_type_filter(self, rf, post_index_page):
        url = post_index_url(rf.get("/"), post_type="blogpost")
        assert url == "/news/?type=blogpost"

    @override_flag("v3", active=True)
    def test_falls_back_when_index_page_is_missing(self, rf, db):
        assert post_index_url(rf.get("/")) == reverse("news")


class TestPostDetailUrl:
    @override_flag("v3", active=False)
    def test_falls_back_to_legacy_detail(self, rf, make_post_page):
        entry, _ = make_post_page()
        assert post_detail_url(rf.get("/"), entry.slug) == reverse(
            "news-detail", args=[entry.slug]
        )

    @override_flag("v3", active=True)
    def test_points_at_the_wagtail_post(self, rf, make_post_page):
        entry, _ = make_post_page()
        assert post_detail_url(rf.get("/"), entry.slug) == f"/news/{entry.slug}/"

    @override_flag("v3", active=True)
    def test_unconverted_entry_keeps_its_legacy_url(
        self, rf, post_index_page, make_entry
    ):
        entry = make_entry(model_class="News", slug="an-entry")
        assert post_detail_url(rf.get("/"), entry.slug) == reverse(
            "news-detail", args=[entry.slug]
        )


class TestLegacyRoutesUnderV3:
    @override_flag("v3", active=True)
    def test_list_redirects_to_the_wagtail_index(self, client, post_index_page):
        response = client.get(reverse("news"))
        assert response.status_code == 302
        assert response.url == "/news/"

    @override_flag("v3", active=True)
    def test_typed_list_redirects_with_its_filter(self, client, post_index_page):
        response = client.get(reverse("news-blogpost-list"))
        assert response.status_code == 302
        assert response.url == "/news/?type=blogpost"

    @override_flag("v3", active=True)
    def test_detail_redirects_to_the_wagtail_post(self, client, make_post_page):
        entry, _ = make_post_page()
        response = client.get(reverse("news-detail", args=[entry.slug]))
        assert response.status_code == 302
        assert response.url == f"/news/{entry.slug}/"

    @override_flag("v3", active=True)
    def test_detail_without_a_wagtail_page_still_serves(
        self, client, post_index_page, make_entry
    ):
        entry = make_entry(model_class="News", slug="an-entry")
        response = client.get(reverse("news-detail", args=[entry.slug]))
        assert response.status_code == 200

    @override_flag("v3", active=False)
    def test_list_serves_legacy_when_the_flag_is_off(self, client, post_index_page):
        response = client.get(reverse("news"))
        assert response.status_code == 200

    @override_flag("v3", active=False)
    def test_detail_serves_legacy_when_the_flag_is_off(self, client, make_post_page):
        entry, _ = make_post_page()
        response = client.get(reverse("news-detail", args=[entry.slug]))
        assert response.status_code == 200


class TestPostCardSources:
    @override_flag("v3", active=True)
    def test_cards_come_from_wagtail_under_v3(self, rf, make_post_page):
        entry, page = make_post_page()
        cards = get_latest_post_cards(limit=3, request=rf.get("/"))
        assert [card["url"] for card in cards] == [f"/news/{page.slug}/"]

    @override_flag("v3", active=False)
    def test_cards_come_from_entries_when_the_flag_is_off(self, rf, make_post_page):
        entry, _ = make_post_page()
        cards = get_latest_post_cards(limit=3, request=rf.get("/"))
        assert [card["url"] for card in cards] == [entry.get_absolute_url()]


class TestHeaderNav:
    @override_flag("v3", active=True)
    def test_posts_link_points_at_wagtail(self, rf, post_index_page):
        links = header_context(rf.get("/"))["nav_links"]
        assert next(link.url for link in links if link.nav_id == "news") == "/news/"

    @override_flag("v3", active=False)
    def test_posts_link_stays_legacy(self, rf, post_index_page):
        links = header_context(rf.get("/"))["nav_links"]
        assert next(link.url for link in links if link.nav_id == "news") == reverse(
            "news"
        )


class TestWagtailIndexRouting:
    @override_flag("v3", active=False)
    def test_entry_without_a_page_is_served_by_the_index(
        self, client, post_index_page, make_entry
    ):
        entry = make_entry(model_class="News", slug="an-entry")
        response = client.get(f"/news/{entry.slug}/")
        assert response.status_code == 200

    @override_flag("v3", active=True)
    def test_entry_without_a_page_is_not_reachable_under_v3(
        self, client, post_index_page, make_entry
    ):
        entry = make_entry(model_class="News", slug="an-entry")
        response = client.get(f"/news/{entry.slug}/")
        assert response.status_code == 404
