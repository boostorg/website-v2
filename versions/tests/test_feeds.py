from datetime import datetime
from django.utils.timezone import make_aware, utc
from ..feeds import RSSVersionFeed, AtomVersionFeed


def test_items(version, old_version):
    feed = RSSVersionFeed()
    items = feed.items()
    assert len(items) == 2
    # Assert sorting
    assert items[0] == version
    # Assert all versions are present
    assert old_version in items


def test_item_pubdate(version):
    feed = RSSVersionFeed()
    expected_datetime = make_aware(
        datetime.combine(version.release_date, datetime.min.time()), timezone=utc
    )
    assert feed.item_pubdate(version) == expected_datetime


def test_item_description_with_release_notes(version, rendered_content):
    rendered_content.cache_key = version.release_notes_cache_key
    rendered_content.save()
    feed = RSSVersionFeed()
    assert feed.item_description(version) == rendered_content.content_html


def test_item_description_without_release_notes(version):
    feed = RSSVersionFeed()
    assert feed.item_description(version) is None


def test_item_title(version):
    feed = RSSVersionFeed()
    assert feed.item_title(version) == f"Version {version.display_name}"


def test_items_atom(version, old_version):
    feed = AtomVersionFeed()
    items = feed.items()
    assert len(items) == 2
    # Assert sorting
    assert items[0] == version
    # Assert all versions are present
    assert old_version in items


def test_item_pubdate_atom(version):
    feed = AtomVersionFeed()
    expected_datetime = make_aware(
        datetime.combine(version.release_date, datetime.min.time()), timezone=utc
    )
    assert feed.item_pubdate(version) == expected_datetime
