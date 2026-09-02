import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils.timezone import now
from model_bakery import baker
from wagtail.models import Collection
from wagtail.models import Locale
from wagtail.models import Page
from waffle.testutils import override_flag

from news.services import get_latest_post_cards
from pages.mixins import ContentTag
from pages.models import PostIndexPage
from pages.models import PostPage
from pages.models import RoutableHomePage

pytestmark = pytest.mark.django_db


@pytest.fixture
def post_index_page(db):
    Locale.objects.get_or_create(language_code="en")
    if not Collection.get_first_root_node():
        Collection.add_root(name="Root")
    root = Page.add_root(instance=Page(title="Root", slug="root"))
    home = root.add_child(instance=RoutableHomePage(title="Home", slug="home"))
    return home.add_child(instance=PostIndexPage(title="Posts", slug="posts"))


@pytest.fixture
def make_post_page(post_index_page, make_user):
    def _make_it(title, tag_slugs=(), live=True, published_at=None, owner=None):
        page = PostPage(
            title=title,
            owner=owner or make_user(email=f"{title.replace(' ', '-')}@example.com"),
            live=live,
            content=[("news", "<p>Body</p>")],
            first_published_at=published_at or now(),
        )
        post_index_page.add_child(instance=page)
        for slug in tag_slugs:
            tag, _ = ContentTag.objects.get_or_create(
                slug=slug, defaults={"name": slug}
            )
            page.tags.add(tag)
        page.save()
        return page

    return _make_it


class TestLatestPostCardsScopedToALibrary:
    @override_flag("v3", active=True)
    def test_returns_only_posts_tagged_with_the_library(self, rf, make_post_page):
        make_post_page("Tagged post", tag_slugs=["multi_array"])
        make_post_page("Other library post", tag_slugs=["beast"])
        make_post_page("Untagged post")

        cards = get_latest_post_cards(request=rf.get("/"), library_slug="multi_array")

        assert [card["title"] for card in cards] == ["Tagged post"]

    @override_flag("v3", active=True)
    def test_card_shape(self, rf, make_post_page):
        page = make_post_page("Tagged post", tag_slugs=["multi_array"])

        (card,) = get_latest_post_cards(request=rf.get("/"), library_slug="multi_array")

        assert card["title"] == "Tagged post"
        assert card["url"] == page.get_absolute_url()
        assert card["date"] == page.first_published_at
        assert card["author"] == page.owner.to_v3_profile_dict()

    @override_flag("v3", active=True)
    def test_card_meta_matches_the_post_list(self, rf, make_post_page):
        """Type in one slot, library in the other, as rendered at /news/."""
        make_post_page("Tagged post", tag_slugs=["multi_array"])

        (card,) = get_latest_post_cards(request=rf.get("/"), library_slug="multi_array")

        assert card["category"] == "News"
        assert card["tag"] == "multi_array"

    @override_flag("v3", active=True)
    def test_omitting_the_slug_still_returns_every_post(self, rf, make_post_page):
        make_post_page("Tagged post", tag_slugs=["multi_array"])
        make_post_page("Untagged post")

        cards = get_latest_post_cards(request=rf.get("/"))

        assert len(cards) == 2

    @override_flag("v3", active=True)
    def test_excludes_unpublished_posts(self, rf, make_post_page):
        make_post_page("Draft post", tag_slugs=["multi_array"], live=False)

        cards = get_latest_post_cards(request=rf.get("/"), library_slug="multi_array")

        assert cards == []

    @override_flag("v3", active=True)
    def test_newest_first_and_limited(self, rf, make_post_page):
        import datetime

        base = now()
        for index in range(4):
            make_post_page(
                f"Post {index}",
                tag_slugs=["multi_array"],
                published_at=base - datetime.timedelta(days=index),
            )

        cards = get_latest_post_cards(
            limit=3, request=rf.get("/"), library_slug="multi_array"
        )

        assert [card["title"] for card in cards] == ["Post 0", "Post 1", "Post 2"]

    @override_flag("v3", active=True)
    def test_no_matching_posts_returns_empty_list(self, rf, make_post_page):
        make_post_page("Other library post", tag_slugs=["beast"])

        cards = get_latest_post_cards(request=rf.get("/"), library_slug="multi_array")

        assert cards == []

    @override_flag("v3", active=True)
    def test_blank_slug_returns_empty_list(self, rf, make_post_page):
        make_post_page("Tagged post", tag_slugs=["multi_array"])

        assert get_latest_post_cards(request=rf.get("/"), library_slug="") == []

    @override_flag("v3", active=False)
    def test_legacy_entries_are_never_returned_unfiltered(
        self, rf, make_post_page, make_entry
    ):
        make_entry()

        cards = get_latest_post_cards(request=rf.get("/"), library_slug="multi_array")

        assert cards == []


def test_post_card_links_the_author_profile(make_entry):
    author = baker.make("users.User", display_name="Jane Doe", image=None)
    make_entry(author=author)
    card = get_latest_post_cards(limit=1)[0]
    assert card["author"]["profile_url"] == author.get_absolute_url()


def test_post_card_does_not_link_a_deactivated_author(make_entry):
    """A deactivated author's profile 404s, so the card leaves the name plain."""
    author = baker.make("users.User", display_name="Jane Doe", image=None)
    make_entry(author=author)
    author.is_active = False
    author.save(update_fields=["is_active"])

    card = get_latest_post_cards(limit=1)[0]
    assert card["author"]["profile_url"] is None


def test_post_card_links_an_unclaimed_author_to_github(make_entry):
    """An unclaimed account is a stub whose profile page is an empty shell, so
    the card points at the GitHub profile the same way contributor rows do."""
    author = baker.make(
        "users.User",
        display_name="Jane Doe",
        image=None,
        claimed=False,
        github_username="janedoe",
    )
    make_entry(author=author)

    card = get_latest_post_cards(limit=1)[0]
    assert card["author"]["profile_url"] == "https://github.com/janedoe"


def test_post_card_leaves_an_unclaimed_author_without_github_unlinked(make_entry):
    author = baker.make(
        "users.User",
        display_name="Jane Doe",
        image=None,
        claimed=False,
        github_username="",
    )
    make_entry(author=author)

    card = get_latest_post_cards(limit=1)[0]
    assert card["author"]["profile_url"] is None


def test_post_cards_fetch_routing_keys_in_one_query(make_entry):
    """Linking each author must not cost a query per card.

    Asserted against the routing-key table specifically rather than a total
    query count, which this service inflates for unrelated reasons.
    """
    for i in range(3):
        make_entry(
            author=baker.make("users.User", display_name=f"User {i}", image=None)
        )

    with CaptureQueriesContext(connection) as queries:
        cards = get_latest_post_cards(limit=3)

    assert len(cards) == 3
    assert all(card["author"]["profile_url"] for card in cards)
    key_queries = [
        query["sql"]
        for query in queries.captured_queries
        if "users_userprofileroutingkey" in query["sql"]
    ]
    assert len(key_queries) == 1, key_queries
