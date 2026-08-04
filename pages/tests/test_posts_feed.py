import re

import pytest
import waffle.testutils
from model_bakery import baker

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def v3_flag():
    """The feed is a V3Mixin page, so it 404s unless the flag is active."""
    with waffle.testutils.override_flag("v3", active=True):
        yield


@pytest.fixture
def feed_url(post_index_page, wagtail_site):
    return post_index_page.url


@pytest.fixture
def beast(db):
    return baker.make("libraries.Library", name="Beast", slug="beast")


def radio_tag(content, value):
    """The rendered <input type=radio> carrying the given value."""
    match = re.search(rf'<input[^>]*value="{value}"[^>]*>', content)
    assert match, f"no radio rendered for {value}"
    return match.group(0)


def titles(response):
    return {post.title for post in response.context["entry_list"]}


def get_feed(tp, feed_url, **params):
    query = "&".join(f"{name}={value}" for name, value in params.items())
    response = tp.get(f"{feed_url}?{query}" if query else feed_url)
    tp.response_200(response)
    return response


class TestSearch:
    def test_matches_title(self, tp, feed_url, make_post_page):
        make_post_page(title="Boost.SQLite proposal results")
        make_post_page(title="Something else entirely")

        assert titles(get_feed(tp, feed_url, q="proposal")) == {
            "Boost.SQLite proposal results"
        }

    def test_dotted_names_match_whole(self, tp, feed_url, make_post_page):
        """Postgres indexes "Boost.SQLite" as one lexeme, so the qualified name
        matches but the bare "SQLite" does not. Library-tagged posts are still
        reachable through the tag index."""
        make_post_page(title="Boost.SQLite proposal results")

        assert titles(get_feed(tp, feed_url, q="Boost.SQLite")) == {
            "Boost.SQLite proposal results"
        }
        assert titles(get_feed(tp, feed_url, q="SQLite")) == set()

    def test_matches_body(self, tp, feed_url, make_post_page):
        make_post_page(title="A Post", body="asio networking is covered here")
        make_post_page(title="Another Post", body="unrelated prose")

        assert titles(get_feed(tp, feed_url, q="networking")) == {"A Post"}

    def test_matches_post_type(self, tp, feed_url, make_post_page):
        make_post_page(title="A Talk", block="video", body="https://example.com/v")
        make_post_page(title="A News Item", block="news")

        assert titles(get_feed(tp, feed_url, q="video")) == {"A Talk"}

    def test_matches_author_name(self, tp, feed_url, make_post_page):
        author = baker.make("users.User", display_name="Vinnie Falco")
        make_post_page(title="Authored Post", owner=author)
        make_post_page(title="Orphan Post")

        assert titles(get_feed(tp, feed_url, q="Falco")) == {"Authored Post"}

    @pytest.mark.parametrize("term", ["beast", "Beast"])
    def test_matches_library_tag(self, tp, feed_url, make_post_page, term):
        make_post_page(title="Tagged Post", tags=[("beast", "Beast")])
        make_post_page(title="Untagged Post")

        assert titles(get_feed(tp, feed_url, q=term)) == {"Tagged Post"}

    def test_does_not_match_markup(self, tp, feed_url, make_post_page):
        """search_body strips tags; indexing the raw block would let a search
        for "p" match every rich text post through its <p> wrappers."""
        make_post_page(title="Markup Post", block="rich_text", body="<p>hello</p>")

        assert titles(get_feed(tp, feed_url, q="p")) == set()

    @pytest.mark.parametrize("term", ["", "%20%20"])
    def test_blank_term_returns_the_whole_feed(
        self, tp, feed_url, make_post_page, term
    ):
        """The backend turns an empty query into zero results rather than into
        "everything", so a blank search has to skip the search path."""
        make_post_page(title="First Post")
        make_post_page(title="Second Post")

        assert titles(get_feed(tp, feed_url, q=term)) == {"First Post", "Second Post"}

    def test_no_matches_returns_nothing(self, tp, feed_url, make_post_page):
        make_post_page(title="First Post")

        assert titles(get_feed(tp, feed_url, q="zzzznomatch")) == set()


class TestFilters:
    def test_filters_by_post_type(self, tp, feed_url, make_post_page):
        make_post_page(title="A News Item", block="news")
        make_post_page(title="A Talk", block="video", body="https://example.com/v")

        assert titles(get_feed(tp, feed_url, type="news")) == {"A News Item"}

    def test_blogpost_filter_spans_both_blocks(self, tp, feed_url, make_post_page):
        make_post_page(title="Markdown Blog", block="blog", body="body")
        make_post_page(title="Rich Text Blog", block="rich_text", body="<p>body</p>")
        make_post_page(title="A News Item", block="news")

        assert titles(get_feed(tp, feed_url, type="blogpost")) == {
            "Markdown Blog",
            "Rich Text Blog",
        }

    def test_filters_by_library(self, tp, feed_url, make_post_page, beast):
        make_post_page(title="Tagged Post", tags=[("beast", "Beast")])
        make_post_page(title="Untagged Post")

        assert titles(get_feed(tp, feed_url, library="beast")) == {"Tagged Post"}

    def test_filters_by_author(self, tp, feed_url, make_post_page):
        author = baker.make("users.User", display_name="Vinnie Falco")
        make_post_page(title="Authored Post", owner=author)
        make_post_page(title="Orphan Post")

        assert titles(get_feed(tp, feed_url, author=author.pk)) == {"Authored Post"}

    @pytest.mark.parametrize(
        "params",
        [
            {"type": "nonsense"},
            {"library": "not-a-library"},
            {"author": "abc"},
            {"author": "999999"},
        ],
    )
    def test_unknown_values_fall_back_to_the_full_feed(
        self, tp, feed_url, make_post_page, params
    ):
        make_post_page(title="First Post")

        response = get_feed(tp, feed_url, **params)

        assert titles(response) == {"First Post"}
        assert response.context["header_text"] == "Latest Posts"


class TestFilterCombinations:
    """The search backend rejects StreamField lookups with an AttributeError
    and tag lookups with a FilterFieldError, so each combination of a search
    term with a filter is a regression test for the pk-subquery workaround."""

    def test_search_with_post_type(self, tp, feed_url, make_post_page):
        make_post_page(title="Networking News", block="news", body="asio networking")
        make_post_page(title="Networking Blog", block="blog", body="asio networking")

        assert titles(get_feed(tp, feed_url, q="networking", type="news")) == {
            "Networking News"
        }

    def test_search_with_library(self, tp, feed_url, make_post_page, beast):
        make_post_page(
            title="Tagged Networking", body="asio networking", tags=[("beast", "Beast")]
        )
        make_post_page(title="Untagged Networking", body="asio networking")

        assert titles(get_feed(tp, feed_url, q="networking", library="beast")) == {
            "Tagged Networking"
        }

    def test_every_filter_at_once(self, tp, feed_url, make_post_page, beast):
        author = baker.make("users.User", display_name="Vinnie Falco")
        make_post_page(
            title="The One",
            block="news",
            body="asio networking",
            owner=author,
            tags=[("beast", "Beast")],
        )
        make_post_page(title="Wrong Type", block="blog", body="asio networking")

        response = get_feed(
            tp,
            feed_url,
            q="networking",
            type="news",
            library="beast",
            author=author.pk,
        )

        assert titles(response) == {"The One"}

    def test_post_type_with_library(self, tp, feed_url, make_post_page, beast):
        make_post_page(title="Tagged News", block="news", tags=[("beast", "Beast")])
        make_post_page(title="Untagged News", block="news")

        assert titles(get_feed(tp, feed_url, type="news", library="beast")) == {
            "Tagged News"
        }


class TestFeedHeader:
    def test_default(self, tp, feed_url):
        assert get_feed(tp, feed_url).context["header_text"] == "Latest Posts"

    def test_search(self, tp, feed_url):
        response = get_feed(tp, feed_url, q="asio")

        assert response.context["header_text"] == 'Results for "asio"'

    def test_post_type(self, tp, feed_url):
        response = get_feed(tp, feed_url, type="news")

        assert response.context["header_text"] == "News Posts"

    def test_blogpost_reads_as_blog(self, tp, feed_url):
        """content_type is "Blogpost", which would render "Blogpost Posts"."""
        response = get_feed(tp, feed_url, type="blogpost")

        assert response.context["header_text"] == "Blog Posts"

    def test_library(self, tp, feed_url, beast):
        response = get_feed(tp, feed_url, library="beast")

        assert response.context["header_text"] == "Boost.Beast Posts"

    def test_post_type_takes_precedence_over_library(self, tp, feed_url, beast):
        response = get_feed(tp, feed_url, type="news", library="beast")

        assert response.context["header_text"] == "News Posts"

    def test_author(self, tp, feed_url):
        author = baker.make("users.User", display_name="Vinnie Falco")

        response = get_feed(tp, feed_url, author=author.pk)

        assert response.context["header_text"] == "Posts by Vinnie Falco"

    def test_search_term_is_escaped(self, tp, feed_url):
        response = get_feed(tp, feed_url, q="<script>alert(1)</script>")

        assert b"<script>alert(1)</script>" not in response.content


class TestPagination:
    def test_paginates(self, tp, feed_url, make_post_page):
        for number in range(12):
            make_post_page(title=f"Post {number}")

        assert len(get_feed(tp, feed_url).context["entry_list"]) == 10
        assert len(get_feed(tp, feed_url, page=2).context["entry_list"]) == 2

    def test_out_of_range_page_clamps(self, tp, feed_url, make_post_page):
        make_post_page(title="Only Post")

        assert titles(get_feed(tp, feed_url, page=999)) == {"Only Post"}

    def test_hidden_when_nothing_matches(self, tp, feed_url, make_post_page):
        """The paginator still reports one page for an empty result set, so
        without the guard the empty state would sit above a lone "1"."""
        make_post_page(title="Only Post")

        assert b"pagination-nav" in get_feed(tp, feed_url).content
        assert b"pagination-nav" not in get_feed(tp, feed_url, q="zzzznomatch").content

    def test_form_does_not_submit_the_current_page(self, tp, feed_url):
        """Pagination resets because page is not a field of the filter form."""
        response = get_feed(tp, feed_url, page=1)

        assert b'name="page"' not in response.content


class TestEmptyState:
    def test_renders_when_nothing_matches(self, tp, feed_url, make_post_page):
        make_post_page(title="First Post")

        response = get_feed(tp, feed_url, q="zzzznomatch")

        assert b"post-empty-state" in response.content

    def test_related_posts_keep_library_and_type(
        self, tp, feed_url, make_post_page, beast
    ):
        related = make_post_page(
            title="Beast News", block="news", tags=[("beast", "Beast")]
        )
        make_post_page(title="Beast Blog", block="blog", tags=[("beast", "Beast")])
        make_post_page(title="Unrelated News", block="news")

        response = get_feed(tp, feed_url, q="zzzznomatch", type="news", library="beast")

        assert response.context["related_posts"] == [related]

    def test_related_posts_fall_back_to_library_only(
        self, tp, feed_url, make_post_page, beast
    ):
        related = make_post_page(
            title="Beast News", block="news", tags=[("beast", "Beast")]
        )

        response = get_feed(
            tp, feed_url, q="zzzznomatch", type="video", library="beast"
        )

        assert response.context["related_posts"] == [related]

    def test_no_related_posts_without_a_library(self, tp, feed_url, make_post_page):
        """Falling back to every post would read as "no results, here is
        everything" rather than as a suggestion."""
        make_post_page(title="First Post")

        response = get_feed(tp, feed_url, q="zzzznomatch")

        assert response.context["related_posts"] == []

    def test_renders_for_an_empty_feed(self, tp, feed_url):
        response = get_feed(tp, feed_url)

        assert b"post-empty-state" in response.content
        assert "related_posts" not in response.context


class TestUrlDrivenState:
    def test_post_type_pill_is_checked(self, tp, feed_url):
        content = get_feed(tp, feed_url, type="news").content.decode()

        assert "checked" in radio_tag(content, "news")
        assert "checked" not in radio_tag(content, "video")

    def test_library_option_is_selected(self, tp, feed_url, beast):
        response = get_feed(tp, feed_url, library="beast").content.decode()

        assert 'value="beast"' in response
        assert "selected" in response

    def test_search_term_is_rendered(self, tp, feed_url):
        response = get_feed(tp, feed_url, q="asio").content.decode()

        assert 'value="asio"' in response

    def test_author_is_carried_in_a_hidden_field(self, tp, feed_url):
        author = baker.make("users.User", display_name="Vinnie Falco")

        response = get_feed(tp, feed_url, author=author.pk).content.decode()

        assert f'name="author" value="{author.pk}"' in response


class TestUserCard:
    def test_logged_in(self, tp, feed_url, user):
        with tp.login(user):
            content = get_feed(tp, feed_url).content.decode()

        assert user.display_name in content
        assert f"Member Since {user.year_joined}" in content
        assert tp.reverse("v3-news-create") in content

    def test_logged_in_card_has_no_placeholder_copy(self, tp, feed_url, user):
        with tp.login(user):
            content = get_feed(tp, feed_url).content.decode()

        assert "Bug Catcher" not in content

    def test_header_nav_links_to_the_feed(self, tp, feed_url):
        """The nav renders a path, not the fully qualified URL Page.url falls
        back to once a second Site exists."""
        content = get_feed(tp, feed_url).content.decode()

        assert f'href="{feed_url}"' in content

    def test_logged_out(self, tp, feed_url):
        content = get_feed(tp, feed_url).content.decode()

        assert "Create an account" in content
        assert "Advance your career, learn from experts" in content
        assert "Sign Up Now" in content
        assert tp.reverse("account_signup") in content


def test_feed_is_hidden_without_the_v3_flag(tp, feed_url):
    with waffle.testutils.override_flag("v3", active=False):
        tp.response_404(tp.get(feed_url))


def test_feed_does_not_scale_queries_with_post_count(
    tp, feed_url, make_post_page, django_assert_max_num_queries
):
    """Each card reads item.author and item.tag, so without select_related and
    prefetch_related the query count grows with the page size."""
    for number in range(10):
        make_post_page(
            title=f"Post {number}",
            owner=baker.make("users.User", display_name=f"Author {number}"),
            tags=[(f"lib{number}", f"Lib{number}")],
        )

    # A full page of posts costs ~14 queries; one query per post for the author
    # plus two for the tags would put it past 30.
    with django_assert_max_num_queries(16):
        tp.get(feed_url)
