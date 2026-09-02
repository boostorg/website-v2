import pytest

from django.contrib.contenttypes.models import ContentType
from model_bakery import baker
from wagtail.search.models import IndexEntry

from pages.models import PostPage

pytestmark = pytest.mark.django_db


def index_entry_for(page):
    return IndexEntry.objects.get(
        content_type=ContentType.objects.get_for_model(PostPage),
        object_id=str(page.pk),
    )


class TestSearchFields:
    def test_keeps_inherited_page_fields(self):
        """A bare assignment instead of BasePage.search_fields + [...] would
        silently drop the title index and every FilterField Page relies on."""
        declared = {(type(f).__name__, f.field_name) for f in PostPage.search_fields}

        assert ("SearchField", "title") in declared
        assert ("FilterField", "live") in declared
        assert ("FilterField", "first_published_at") in declared

    def test_indexes_the_feed_search_surface(self):
        declared = {(type(f).__name__, f.field_name) for f in PostPage.search_fields}

        assert ("SearchField", "search_body") in declared
        assert ("SearchField", "summary") in declared
        assert ("SearchField", "post_content_type") in declared
        assert ("RelatedFields", "tags") in declared
        assert ("RelatedFields", "owner") in declared

    def test_indexes_an_autocomplete_surface(self):
        """Prefix matching reads a separate vector from SearchField."""
        declared = {(type(f).__name__, f.field_name) for f in PostPage.search_fields}
        owner = next(
            f
            for f in PostPage.search_fields
            if type(f).__name__ == "RelatedFields" and f.field_name == "owner"
        )
        owner_fields = {(type(f).__name__, f.field_name) for f in owner.fields}

        assert ("AutocompleteField", "title") in declared
        assert ("AutocompleteField", "display_name") in owner_fields


class TestSearchBody:
    def test_strips_markup(self, make_post_page):
        page = make_post_page(
            block="rich_text", body="<p>Hello <b>world</b> networking</p>"
        )

        assert page.search_body == "Hello world networking"

    def test_returns_body_text_for_markdown(self, make_post_page):
        page = make_post_page(block="news", body="Boost.SQLite proposal results")

        assert "Boost.SQLite proposal results" in page.search_body

    def test_does_not_raise_for_a_video_post(self, make_post_page):
        page = make_post_page(block="video", body="https://example.com/v")

        assert isinstance(page.search_body, str)


class TestIndexEntry:
    def test_row_is_written_on_save(self, make_post_page):
        page = make_post_page(title="Indexed Post", body="some body text")

        assert index_entry_for(page).body

    def test_indexes_related_tag_and_author(self, make_post_page):
        author = baker.make("users.User", display_name="Vinnie Falco")
        page = make_post_page(owner=author, tags=[("beast", "Beast")])

        # The body column is a stemmed tsvector, so match lexemes not words.
        body = index_entry_for(page).body

        assert "beast" in body
        assert "falco" in body


class TestSearchConfig:
    def test_folds_accents_into_the_indexed_lexemes(self, make_post_page):
        """The config applies at index time, so the stored vector proves it."""
        author = baker.make("users.User", display_name="Rubén Pérez")
        page = make_post_page(owner=author)

        body = index_entry_for(page).body

        assert "perez" in body
        assert "ruben" in body

    def test_backend_is_configured_for_unaccented_search(self):
        """Both vectors, not just the full text one."""
        from modelsearch.backends import get_search_backend

        backend = get_search_backend()

        assert backend.config == "english_unaccent"
        assert backend.autocomplete_config == "simple_unaccent"
