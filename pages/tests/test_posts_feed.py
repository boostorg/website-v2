import re

import pytest
import waffle.testutils
from model_bakery import baker

from pages.feed import PostFeedFilters

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def v3_flag():
    """The feed shares its URL with the legacy Entry list, which is what the
    same URL renders while the flag is off."""
    with waffle.testutils.override_flag("v3", active=True):
        yield


@pytest.fixture
def feed_url(post_index_page, wagtail_site):
    """The feed's URL is the index page's own route.

    Under v3 the Wagtail index page owns the posts URL and the legacy news
    route redirects here, so the site has to exist for the page to resolve to
    a URL at all.
    """
    return post_index_page.get_url()


@pytest.fixture
def beast(db):
    return baker.make("libraries.Library", name="Beast", slug="beast")


def input_tag(content, attribute):
    """The rendered <input> carrying the given attribute.

    Anchors an assertion to one field: every value the feed echoes back also
    appears somewhere in the filter dropdown, so a bare substring match on the
    whole page passes whether or not the querystring was read.
    """
    match = re.search(rf"<input[^>]*{re.escape(attribute)}[^>]*>", content)
    assert match, f"no input rendered with {attribute}"
    return match.group(0)


def radio_tag(content, value):
    """The rendered <input type=radio> carrying the given value."""
    return input_tag(content, f'value="{value}"')


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

    @pytest.mark.parametrize("term", ["Rob", "Robe", "Fal", "vinn"])
    def test_matches_a_partial_author_name(self, tp, feed_url, make_post_page, term):
        """Full text matches whole stemmed words, so a prefix found nothing."""
        author = baker.make("users.User", display_name="Robert Vinnie Falco")
        make_post_page(title="Authored Post", owner=author)
        make_post_page(title="Orphan Post")

        assert titles(get_feed(tp, feed_url, q=term)) == {"Authored Post"}

    def test_matches_a_partial_title(self, tp, feed_url, make_post_page):
        make_post_page(title="Boost.SQLite proposal results")
        make_post_page(title="Something else entirely")

        assert titles(get_feed(tp, feed_url, q="propos")) == {
            "Boost.SQLite proposal results"
        }

    def test_prefers_whole_word_matches_over_prefixes(
        self, tp, feed_url, make_post_page
    ):
        """The prefix pass is a fallback, so whole-word matches are not widened."""
        falco = baker.make("users.User", display_name="Vinnie Falco")
        falconer = baker.make("users.User", display_name="Ada Falconer")
        make_post_page(title="Falco Post", owner=falco)
        make_post_page(title="Falconer Post", owner=falconer)

        assert titles(get_feed(tp, feed_url, q="Falco")) == {"Falco Post"}

    @pytest.mark.parametrize("term", ["p", "ab"])
    def test_does_not_run_the_prefix_pass_for_very_short_terms(
        self, tp, feed_url, make_post_page, term
    ):
        """One or two letters prefix most of the feed."""
        make_post_page(title="Post About Absolutely Everything")

        assert titles(get_feed(tp, feed_url, q=term)) == set()

    @pytest.mark.parametrize("term", ["Perez", "Pérez", "perez", "PEREZ"])
    def test_matches_an_accented_author_name_either_spelling(
        self, tp, feed_url, make_post_page, term
    ):
        """Stock `english` makes "perez" and "pérez" different lexemes."""
        author = baker.make("users.User", display_name="Rubén Pérez")
        make_post_page(title="Authored Post", owner=author)
        make_post_page(title="Orphan Post")

        assert titles(get_feed(tp, feed_url, q=term)) == {"Authored Post"}

    @pytest.mark.parametrize("term", ["Lope", "Lópe", "Muno", "Muñ"])
    def test_matches_a_partial_accented_author_name_either_spelling(
        self, tp, feed_url, make_post_page, term
    ):
        """The prefix vector unaccents too, so "Lope" reaches "López"."""
        author = baker.make("users.User", display_name="Joaquín M López Muñoz")
        make_post_page(title="Authored Post", owner=author)
        make_post_page(title="Orphan Post")

        assert titles(get_feed(tp, feed_url, q=term)) == {"Authored Post"}

    def test_leaves_non_latin_scripts_alone(self, tp, feed_url, make_post_page):
        """`unaccent` passes through what it cannot fold."""
        author = baker.make("users.User", display_name="Ольга Иванова")
        make_post_page(title="Cyrillic Post", owner=author)

        assert titles(get_feed(tp, feed_url, q="Ольга")) == {"Cyrillic Post"}

    def test_returns_nothing_for_a_term_that_matches_neither_way(
        self, tp, feed_url, make_post_page
    ):
        make_post_page(title="A Post", body="asio networking")

        assert titles(get_feed(tp, feed_url, q="xylophone")) == set()

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
            {"page": "999"},
        ],
    )
    def test_unresolvable_values_fall_back_to_the_full_feed(
        self, tp, feed_url, make_post_page, params
    ):
        """Anything the querystring cannot resolve degrades to the unfiltered
        feed rather than erroring or emptying it."""
        make_post_page(title="First Post")

        response = get_feed(tp, feed_url, **params)

        assert titles(response) == {"First Post"}
        assert response.context["header_text"] == "Latest Posts"


class TestLibraryFilterOptions:
    """The dropdown offers only libraries a live post is tagged with.

    Every other library narrows the feed to nothing and nothing else, so
    listing them all buries the handful that lead somewhere.
    """

    @staticmethod
    def options(response):
        return response.context["library_options"]

    def test_offers_a_tagged_library(self, tp, feed_url, make_post_page, beast):
        make_post_page(title="Tagged Post", tags=[("beast", "Beast")])

        assert self.options(get_feed(tp, feed_url)) == [("beast", "Boost.Beast")]

    def test_omits_an_untagged_library(self, tp, feed_url, make_post_page, beast):
        make_post_page(title="Untagged Post")

        assert self.options(get_feed(tp, feed_url)) == []

    def test_omits_a_library_tagged_only_on_a_draft(
        self, tp, feed_url, make_post_page, beast
    ):
        """A draft is not in the feed, so filtering by its library would come
        back empty."""
        make_post_page(title="Draft Post", tags=[("beast", "Beast")], live=False)

        assert self.options(get_feed(tp, feed_url)) == []

    def test_lists_a_library_once_however_many_posts_carry_it(
        self, tp, feed_url, make_post_page, beast
    ):
        """The tagged slugs arrive as a subquery over one row per post/tag
        pair, which duplicates the library without the IN."""
        make_post_page(title="First Post", tags=[("beast", "Beast")])
        make_post_page(title="Second Post", tags=[("beast", "Beast")])

        assert self.options(get_feed(tp, feed_url)) == [("beast", "Boost.Beast")]

    def test_orders_by_name(self, tp, feed_url, make_post_page):
        baker.make("libraries.Library", name="Beast", slug="beast")
        baker.make("libraries.Library", name="Asio", slug="asio")
        make_post_page(
            title="Tagged Twice", tags=[("beast", "Beast"), ("asio", "Asio")]
        )

        assert [slug for slug, _ in self.options(get_feed(tp, feed_url))] == [
            "asio",
            "beast",
        ]

    def test_omits_a_tag_no_library_answers_to(self, tp, feed_url, make_post_page):
        """Posts reach a library by matching slugs rather than by a relation,
        so a tag with no library behind it must not reach the dropdown."""
        make_post_page(title="Oddly Tagged", tags=[("not-a-library", "Not A Library")])

        assert self.options(get_feed(tp, feed_url)) == []


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


class TestFeedHeader:
    """`header_text` is a pure property over parsed filters, so the wording and
    precedence rules are covered against the dataclass rather than by building
    the page tree and going over HTTP once per case."""

    @pytest.mark.parametrize(
        "params,expected",
        [
            ({}, "Latest Posts"),
            ({"q": "asio"}, 'Results for "asio"'),
            ({"type": "news"}, "News Posts"),
            # content_type is "Blogpost", which would read "Blogpost Posts".
            ({"type": "blogpost"}, "Blog Posts"),
            ({"library": "beast"}, "Boost.Beast Posts"),
            # Type beats library, and search beats both.
            ({"type": "news", "library": "beast"}, "News Posts"),
            ({"q": "asio", "type": "news", "library": "beast"}, 'Results for "asio"'),
        ],
    )
    def test_wording_and_precedence(self, rf, beast, params, expected):
        filters = PostFeedFilters.from_request(rf.get("/", params))

        assert filters.header_text == expected

    def test_author(self, rf):
        author = baker.make("users.User", display_name="Vinnie Falco")

        filters = PostFeedFilters.from_request(rf.get("/", {"author": author.pk}))

        assert filters.header_text == "Posts by Vinnie Falco"

    def test_search_term_is_escaped(self, tp, feed_url):
        """The header case that genuinely needs the template rendered."""
        response = get_feed(tp, feed_url, q="<script>alert(1)</script>")

        assert b"<script>alert(1)</script>" not in response.content


class TestPostCard:
    """The type chip on a card. "Blogpost" is the internal name of the type and
    should never reach a reader."""

    def test_type_is_worded_for_a_reader(self, tp, feed_url, make_post_page):
        make_post_page(title="Echo server with Asio", block="blog", tags=["asio"])

        content = get_feed(tp, feed_url).content.decode()

        assert "<span>Blog</span>" in content
        assert "Blogpost" not in content

    def test_untagged_post_shows_the_type_but_no_tag(
        self, tp, feed_url, make_post_page
    ):
        """A post with no tags carries no tag chip. The type chip stays, so
        the row does not read as though something failed to load."""
        make_post_page(title="Echo server with Asio", block="blog")

        content = get_feed(tp, feed_url).content.decode()

        assert "<span>Blog</span>" in content
        assert "<span>#" not in content


class TestPagination:
    def test_paginates(self, tp, feed_url, make_post_page):
        for number in range(12):
            make_post_page(title=f"Post {number}")

        assert len(get_feed(tp, feed_url).context["entry_list"]) == 10
        assert len(get_feed(tp, feed_url, page=2).context["entry_list"]) == 2

    def test_hidden_when_nothing_matches(self, tp, feed_url, make_post_page):
        """The paginator still reports one page for an empty result set, so
        without the guard the empty state would sit above a lone "1"."""
        make_post_page(title="Only Post")

        assert b"pagination-nav" in get_feed(tp, feed_url).content
        assert b"pagination-nav" not in get_feed(tp, feed_url, q="zzzznomatch").content


class TestEmptyState:
    def test_renders_when_nothing_matches(self, tp, feed_url, make_post_page):
        make_post_page(title="First Post")

        response = get_feed(tp, feed_url, q="zzzznomatch")

        assert b"empty-state" in response.content
        assert b"No results, please search again..." in response.content
        assert b"Try a shorter keyword, or check the spelling." in response.content

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

        assert b"empty-state" in response.content
        assert b"No results, please search again..." in response.content
        assert "related_posts" not in response.context


class TestUrlDrivenState:
    def test_post_type_pill_is_checked(self, tp, feed_url):
        content = get_feed(tp, feed_url, type="news").content.decode()

        assert "checked" in radio_tag(content, "news")
        assert "checked" not in radio_tag(content, "video")

    def test_library_option_is_selected(self, tp, feed_url, make_post_page, beast):
        """The word "selected" appears in the dropdown's Alpine bindings
        whether or not anything is chosen, so both halves of the control have
        to be checked against the value itself.

        The post is what puts Boost.Beast in the dropdown at all: only
        libraries a live post carries are offered.
        """
        make_post_page(title="Tagged Post", tags=[("beast", "Beast")])

        content = get_feed(tp, feed_url, library="beast").content.decode()

        assert 'value="beast" selected' in content
        assert "selected: 'beast'" in content

    def test_search_term_is_rendered(self, tp, feed_url):
        """Anchored to the search input: "asio" is also a library slug sitting
        in the dropdown, so a bare substring match would pass without `?q=`."""
        content = get_feed(tp, feed_url, q="asio").content.decode()

        assert 'value="asio"' in input_tag(content, 'id="field-q"')

    def test_search_submits_on_its_own_after_a_pause(self, tp, feed_url):
        """Typing filters the feed without reaching for Enter or the arrow.

        The quiet period is longer than the library list's because a search
        here costs a round trip, so the number is asserted rather than just
        the presence of a handler.
        """
        content = get_feed(tp, feed_url).content.decode()

        assert "@input.debounce.500ms" in input_tag(content, 'id="field-q"')

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

    def test_logged_out(self, tp, feed_url):
        """Only the copy this template owns. The heading and description come
        from `_user_card.html`'s own defaults, and asserting on those here
        would fail a posts feed test over a copy tweak in the include."""
        content = get_feed(tp, feed_url).content.decode()

        assert "Sign Up Now" in content
        assert tp.reverse("account_signup") in content


def test_header_nav_links_to_the_feed(tp, feed_url):
    """One URL for both feeds means the nav link needs no flag of its own."""
    content = get_feed(tp, feed_url).content.decode()

    assert f'href="{feed_url}"' in content


@pytest.mark.parametrize("params", [{}, {"q": "Post"}])
def test_feed_does_not_scale_queries_with_post_count(
    tp, feed_url, make_post_page, django_assert_max_num_queries, params
):
    """Each card reads item.author and item.tag, so without select_related and
    prefetch_related the query count grows with the page size. The searched
    feed re-enters through a pk subquery, which drops both unless they are
    reapplied, so it needs its own case."""
    for number in range(10):
        make_post_page(
            title=f"Post {number}",
            owner=baker.make("users.User", display_name=f"Author {number}"),
            tags=[(f"lib{number}", f"Lib{number}")],
        )

    # A full page of posts costs ~14 queries; one query per post for the author
    # plus two for the tags would put it past 30.
    with django_assert_max_num_queries(16):
        response = get_feed(tp, feed_url, **params)

    # Guards the search case against passing on an empty result set.
    assert len(response.context["entry_list"]) == 10


class TestFlagSwitch:
    """One URL, two feeds. The flag picks between the legacy Entry list and
    the v3 feed over the PostPage tree, the same way every other v3 page in
    the site swaps its template."""

    def test_flag_on_renders_the_v3_feed(self, tp, feed_url):
        """Wagtail serves the page itself, so it names one template rather
        than the candidate list a Django ListView builds."""
        response = get_feed(tp, feed_url)

        assert response.template_name == "v3/posts_list.html"

    def test_flag_off_renders_the_legacy_list(self, tp, feed_url):
        with waffle.testutils.override_flag("v3", active=False):
            response = tp.get(feed_url)

        tp.response_200(response)
        # ListView appends its own default, so the legacy template is the
        # first candidate rather than the only one.
        assert "news/list.html" in response.template_name

    def test_flag_on_without_an_index_page_renders_the_legacy_list(self, tp):
        """The index page is created by hand in the CMS per environment, and
        the posts it parents are the only thing the v3 feed lists. Until it
        exists the legacy list stays rather than an empty page."""
        response = tp.get("news")

        tp.response_200(response)
        # ListView appends its own default, so the legacy template is the
        # first candidate rather than the only one.
        assert "news/list.html" in response.template_name

    def test_flag_off_still_paginates_the_legacy_list(self, tp, feed_url, make_entry):
        """The v3 branch turns pagination off so it can paginate its own
        results, which must not leak into the legacy list."""
        for number in range(11):
            make_entry("News", title=f"Entry {number}")

        with waffle.testutils.override_flag("v3", active=False):
            response = tp.get(f"{feed_url}?page=2")

        tp.response_200(response)
        assert len(response.context["entry_list"]) == 1


class TestLegacyTypeListRedirect:
    """Under v3 the per-type Entry lists forward to the one feed, so inbound
    links (bookmarks, search results, older notification emails) land there
    filtered instead of on a second URL rendering the same posts."""

    def test_redirect_carries_the_post_type(self, tp, feed_url):
        response = tp.get("news-video-list")

        tp.response_302(response)
        assert response.url == f"{feed_url}?type=video"

    def test_untyped_list_redirects_to_the_bare_feed(self, tp, feed_url):
        """Polls have no v3 content type, so there is no filter to carry."""
        response = tp.get("news-poll-list")

        tp.response_302(response)
        assert response.url == feed_url

    def test_the_feed_does_not_redirect_to_itself(self, tp, feed_url):
        tp.response_200(tp.get(feed_url))

    def test_redirect_is_temporary(self, tp, feed_url):
        """A cached 301 would strand v2 visitors if the flag is switched off."""
        assert tp.get("news-video-list").status_code == 302

    def test_no_redirect_without_the_flag(self, tp, feed_url):
        with waffle.testutils.override_flag("v3", active=False):
            tp.response_200(tp.get("news-video-list"))

    def test_no_redirect_without_an_index_page(self, tp, wagtail_site):
        tp.response_200(tp.get("news-video-list"))
