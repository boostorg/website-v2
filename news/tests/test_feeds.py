from datetime import datetime, timedelta, timezone
from django.utils.timezone import make_aware, now
from model_bakery import baker
from ..feeds import RSSNewsFeed, AtomNewsFeed


def test_items(make_entry):
    earlier = now() - timedelta(days=30)
    newer_entry = make_entry(
        moderator=baker.make("users.User"), approved_at=now(), publish_at=now()
    )
    earlier_entry = make_entry(
        moderator=baker.make("users.User"), approved_at=earlier, publish_at=earlier
    )
    # Unpublished entry
    make_entry(moderator=baker.make("users.User"), approved_at=None)
    feed = RSSNewsFeed()
    items = feed.items()
    assert len(items) == 2
    # Newest first
    assert items[0] == newer_entry
    assert items[1] == earlier_entry


def test_items_returns_newest_when_more_than_limit(make_entry):
    """Regression test for boostorg/website-v2#2362.

    With ascending order + [:100] slice, the feed permanently locked onto the
    100 oldest entries once total count exceeded 100. Confirm newest-first.
    """
    base = now() - timedelta(days=200)
    entries = [
        make_entry(
            moderator=baker.make("users.User"),
            approved_at=base + timedelta(days=i),
            publish_at=base + timedelta(days=i),
        )
        for i in range(101)
    ]
    feed = RSSNewsFeed()
    items = list(feed.items())
    assert len(items) == 100
    assert items[0] == entries[-1]
    assert entries[0] not in items


def test_items_excludes_soft_deleted(make_entry):
    live_entry = make_entry(moderator=baker.make("users.User"), approved_at=now())
    make_entry(
        moderator=baker.make("users.User"),
        approved_at=now(),
        deleted_at=now(),
    )
    feed = RSSNewsFeed()
    items = list(feed.items())
    assert items == [live_entry]


def test_items_excludes_unpublished_even_when_not_deleted(make_entry):
    make_entry(
        moderator=baker.make("users.User"),
        approved_at=None,
        deleted_at=None,
    )
    feed = RSSNewsFeed()
    assert list(feed.items()) == []


def test_item_pubdate(make_entry):
    feed = RSSNewsFeed()
    published_entry = make_entry(moderator=baker.make("users.User"), approved_at=now())
    expected_datetime = make_aware(
        datetime.combine(published_entry.publish_at, datetime.min.time()),
        timezone=timezone.utc,
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
        datetime.combine(published_entry.publish_at, datetime.min.time()),
        timezone=timezone.utc,
    )
    assert feed.item_pubdate(published_entry) == expected_datetime
