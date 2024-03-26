from datetime import datetime, timedelta
from django.utils.timezone import make_aware, now, utc
from model_bakery import baker
from ..feeds import RSSNewsFeed, AtomNewsFeed


def test_items(make_entry):
    earlier = now() - timedelta(days=30)
    published_entry = make_entry(moderator=baker.make("users.User"), approved_at=now())
    earlier_entry = make_entry(moderator=baker.make("users.User"), approved_at=earlier)
    # Unpublished entry
    make_entry(moderator=baker.make("users.User"), approved_at=None)
    feed = RSSNewsFeed()
    items = feed.items()
    assert len(items) == 2
    # Assert sorting
    assert items[0] == published_entry
    assert items[1] == earlier_entry


def test_item_pubdate(make_entry):
    feed = RSSNewsFeed()
    published_entry = make_entry(moderator=baker.make("users.User"), approved_at=now())
    expected_datetime = make_aware(
        datetime.combine(published_entry.publish_at, datetime.min.time()), timezone=utc
    )
    assert feed.item_pubdate(published_entry) == expected_datetime


def test_item_description(make_entry):
    feed = RSSNewsFeed()
    published_entry = make_entry(moderator=baker.make("users.User"), approved_at=now())
    assert feed.item_description(published_entry) == published_entry.content


def test_item_title(make_entry):
    feed = RSSNewsFeed()
    published_entry = make_entry(moderator=baker.make("users.User"), approved_at=now())
    assert feed.item_title(published_entry) == published_entry.title


def test_items_atom(make_entry):
    feed = AtomNewsFeed()
    published_entry = make_entry(moderator=baker.make("users.User"), approved_at=now())
    items = feed.items()
    assert len(items) == 1
    assert items[0] == published_entry


def test_item_pubdate_atom(make_entry):
    feed = AtomNewsFeed()
    published_entry = make_entry(moderator=baker.make("users.User"), approved_at=now())
    expected_datetime = make_aware(
        datetime.combine(published_entry.publish_at, datetime.min.time()), timezone=utc
    )
    assert feed.item_pubdate(published_entry) == expected_datetime
