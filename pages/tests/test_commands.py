import io

import click
import pytest
from django.core import management
from django.core.files.images import ImageFile
from PIL import Image as PILImage
from wagtail.images.models import Image as WagtailImage
from pages.management.commands.convert_news_entries import basic_conversion
from pages.management.commands.convert_news_entries import convert_image
from pages.management.commands.convert_news_entries import convert_text_content
from pages.management.commands.convert_news_entries import get_or_create_page
from pages.models import PostPage


def _attach_image(entry, filename="photo.png"):
    buffer = io.BytesIO()
    PILImage.new("RGB", (50, 50)).save(buffer, "PNG")
    buffer.seek(0)
    entry.image.save(filename, ImageFile(buffer, name=filename), save=True)
    return entry


class TestGetOrCreatePage:
    def test_creates_new_page(self, post_index_page, make_entry):
        entry = make_entry(model_class="News", title="Breaking News")

        page = get_or_create_page(entry, post_index_page)

        assert isinstance(page, PostPage)
        assert page.pk is not None
        assert PostPage.objects.filter(title=entry.title).count() == 1
        assert page.owner == entry.author
        assert page.live == entry.is_published

    def test_is_idempotent_upsert(self, post_index_page, make_entry):
        entry = make_entry(model_class="News", title="Breaking News")

        first = get_or_create_page(entry, post_index_page)
        second = get_or_create_page(entry, post_index_page)

        assert first.pk == second.pk
        assert PostPage.objects.filter(title=entry.title).count() == 1

    def test_updates_existing_page_fields(self, post_index_page, make_entry):
        entry = make_entry(model_class="News", title="Breaking News", published=False)
        page = get_or_create_page(entry, post_index_page)
        page.save()
        assert page.live is False

        entry.moderator = entry.author
        entry.approved_at = entry.publish_at
        entry.publish_at = entry.publish_at
        entry.save()

        updated = get_or_create_page(entry, post_index_page)
        updated.save()

        assert updated.pk == page.pk
        assert updated.live == entry.is_published


class TestConvertImage:
    def test_transfers_image_to_wagtail(self, post_index_page, make_entry):
        entry = make_entry(model_class="News", title="With Image")
        _attach_image(entry)
        page = get_or_create_page(entry, post_index_page)

        convert_image(entry, page)

        page.refresh_from_db()
        assert page.image is not None
        assert page.image.title == entry.image.name
        assert WagtailImage.objects.count() == 1

    def test_is_idempotent_for_same_title(self, post_index_page, make_entry):
        entry = make_entry(model_class="News", title="With Image")
        _attach_image(entry)
        page = get_or_create_page(entry, post_index_page)

        convert_image(entry, page)
        convert_image(entry, page)

        assert WagtailImage.objects.filter(title=entry.image.name).count() == 1


class TestConvertTextContent:
    def test_urlizes_and_wraps_in_paragraphs(self):
        result = convert_text_content(
            "Check https://example.com out\r\nIt is really cool."
        )

        assert "<a href=" in result
        assert "  \r\n" in result
        assert "example.com" in result


class TestBasicConversion:
    def test_sets_summary_and_image(self, post_index_page, make_entry):
        entry = make_entry(model_class="News", title="Full Entry", summary="A summary")
        _attach_image(entry)

        page = basic_conversion(entry, post_index_page)

        assert page.summary == "A summary"
        assert page.image is not None

    def test_missing_image_is_not_an_error(self, post_index_page, make_entry):
        entry = make_entry(model_class="News", title="No Image", summary="A summary")
        assert not entry.image

        page = basic_conversion(entry, post_index_page)

        assert page.image is None


class TestConvertNewsEntriesCommand:
    def test_raises_without_post_index_page(self, db):
        with pytest.raises(click.ClickException):
            management.call_command("convert_news_entries")

    def test_maps_content_blocks_per_entry_type(self, post_index_page, make_entry):
        blog = make_entry(model_class="BlogPost", title="A Blog", content="**bold**")
        news = make_entry(model_class="News", title="A News Item", content="news body")
        video = make_entry(
            model_class="Video", title="A Video", external_url="https://example.com/v"
        )
        link = make_entry(
            model_class="Link", title="A Link", external_url="https://example.com"
        )

        management.call_command("convert_news_entries")

        blog_page = PostPage.objects.get(title=blog.title)
        assert blog_page.content[0].block_type == "blog"
        assert "bold" in blog_page.content[0].value

        news_page = PostPage.objects.get(title=news.title)
        assert news_page.content[0].block_type == "news"
        assert "news body" in news_page.content[0].value

        video_page = PostPage.objects.get(title=video.title)
        assert video_page.content[0].block_type == "video"
        assert video_page.content[0].value.url == video.external_url

        link_page = PostPage.objects.get(title=link.title)
        assert link_page.content[0].block_type == "url"
        assert link_page.content[0].value == link.external_url

    def test_is_idempotent_across_runs(self, post_index_page, make_entry):
        make_entry(model_class="News", title="Repeated News")

        management.call_command("convert_news_entries")
        management.call_command("convert_news_entries")

        assert PostPage.objects.filter(title="Repeated News").count() == 1

    def test_handles_entry_with_no_media(self, post_index_page, make_entry):
        entry = make_entry(model_class="News", title="No Media News")
        assert not entry.image

        management.call_command("convert_news_entries")

        page = PostPage.objects.get(title=entry.title)
        assert page.image is None


class TestUpdateIndexTask:
    def test_runs_the_wagtail_command(self, mocker):
        from pages.tasks import update_index_task

        call_command = mocker.patch("pages.tasks.call_command")

        update_index_task()

        call_command.assert_called_once_with("wagtail_update_index")

    def test_update_index_is_haystacks_no_op(self):
        """Wagtail ships `update_index` as an alias too, but haystack precedes
        it in INSTALLED_APPS and wins the name, which is why the task above
        cannot use it."""
        assert management.get_commands()["update_index"] == "haystack"
