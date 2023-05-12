import datetime

from django.utils.timezone import now
from model_bakery import baker

from ..models import Entry, Poll


def test_entry_str():
    entry = baker.make("Entry")
    assert str(entry) == f"{entry.title} by {entry.author}"


def test_entry_generate_slug():
    author = baker.make("users.User")
    entry = Entry.objects.create(title="😀 Foo Bar Baz!@! +", author=author)
    assert entry.slug == "foo-bar-baz"


def test_entry_slug_not_overwriten():
    author = baker.make("users.User")
    entry = Entry.objects.create(title="Foo!", author=author, slug="different")
    assert entry.slug == "different"


def test_entry_published():
    entry = baker.make("Entry", publish_at=now())
    assert entry.published is True


def test_entry_not_published():
    entry = baker.make("Entry", publish_at=now() + datetime.timedelta(minutes=1))
    assert entry.published is False


def test_entry_absolute_url():
    entry = baker.make("Entry", slug="the-slug")
    assert entry.get_absolute_url() == "/news/the-slug/"


def test_blogpost():
    blogpost = baker.make("BlogPost")
    assert isinstance(blogpost, Entry)
    assert Entry.objects.get(id=blogpost.id).blogpost == blogpost


def test_link():
    link = baker.make("Link")
    assert isinstance(link, Entry)
    assert Entry.objects.get(id=link.id).link == link


def test_video():
    video = baker.make("Video")
    assert isinstance(video, Entry)
    assert Entry.objects.get(id=video.id).video == video


def test_poll():
    poll = baker.make("Poll")
    assert isinstance(poll, Entry)
    assert Entry.objects.get(id=poll.id).poll == poll


def test_poll_choice():
    choice = baker.make("PollChoice")
    assert isinstance(choice.poll, Poll)
