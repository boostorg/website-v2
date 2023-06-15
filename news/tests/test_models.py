import datetime

import pytest
from django.contrib.auth.models import Permission
from django.utils.timezone import now
from model_bakery import baker

from ..models import Entry, Poll


def test_entry_basic():
    entry = baker.make("Entry")
    assert str(entry) == entry.title
    assert entry.news_type is None


def test_entry_generate_slug():
    author = baker.make("users.User")
    entry = Entry.objects.create(title="😀 Foo Bar Baz!@! +", author=author)
    assert entry.slug == "foo-bar-baz"


def test_entry_slug_not_overwriten():
    author = baker.make("users.User")
    entry = Entry.objects.create(title="Foo!", author=author, slug="different")
    assert entry.slug == "different"


def test_entry_approved(make_entry):
    entry = make_entry(moderator=baker.make("users.User"), approved_at=now())
    assert entry.is_approved is True


def test_entry_not_approved(make_entry):
    entry = make_entry(moderator=None, approved_at=now())
    assert entry.is_approved is False

    entry = make_entry(moderator=baker.make("users.User"), approved_at=None)
    assert entry.is_approved is False

    future = now() + datetime.timedelta(minutes=1)
    entry = make_entry(moderator=baker.make("users.User"), approved_at=future)
    assert entry.is_approved is False


def test_entry_published(make_entry):
    entry = make_entry(approved=True, publish_at=now())
    assert entry.is_published is True


def test_entry_not_published(make_entry):
    entry = make_entry(approved=False, publish_at=now())
    assert entry.is_published is False

    future = now() + datetime.timedelta(minutes=1)
    entry = make_entry(approved=True, publish_at=future)
    assert entry.is_published is False


def test_entry_absolute_url(tp):
    entry = baker.make("Entry", slug="the-slug")
    assert entry.get_absolute_url() == tp.reverse("news-detail", "the-slug")


def test_approve_entry(make_entry):
    future = now() + datetime.timedelta(hours=1)
    entry = make_entry(approved=False, publish_at=future)
    assert not entry.is_approved
    assert not entry.is_published

    user = baker.make("users.User")
    before = now()
    entry.approve(user)
    after = now()

    entry.refresh_from_db()
    assert entry.moderator == user
    # Avoid mocking `now()`, yet still ensure that the approval timestamp
    # ocurred between `before` and `after`
    assert entry.approved_at <= after
    assert entry.approved_at >= before
    assert entry.is_approved
    assert not entry.is_published


def test_approve_already_approved_entry(make_entry):
    entry = make_entry(approved=True)
    assert entry.is_approved

    with pytest.raises(Entry.AlreadyApprovedError):
        entry.approve(baker.make("users.User"))


def test_entry_permissions_author(make_entry):
    entry = make_entry(approved=False)
    author = entry.author
    assert entry.can_view(author) is True
    assert entry.can_edit(author) is True
    assert entry.can_delete(author) is False
    assert entry.can_approve(author) is False

    entry.approve(baker.make("users.User"))
    assert entry.can_view(author) is True
    assert entry.can_edit(author) is False
    assert entry.can_delete(author) is False
    assert entry.can_approve(author) is False


def test_not_approved_entry_permissions_other_users(make_entry):
    entry = make_entry(approved=False)
    assert entry.can_view(None) is False
    assert entry.can_edit(None) is False
    assert entry.can_delete(None) is False
    assert entry.can_approve(None) is False

    regular_user = baker.make("users.User")
    assert entry.can_view(regular_user) is False
    assert entry.can_edit(regular_user) is False
    assert entry.can_delete(regular_user) is False
    assert entry.can_approve(regular_user) is False

    superuser = baker.make("users.User", is_superuser=True)
    assert entry.can_view(superuser) is True
    assert entry.can_edit(superuser) is True
    assert entry.can_delete(superuser) is True
    assert entry.can_approve(superuser) is True

    user_with_add_perm = baker.make("users.User")
    user_with_add_perm.user_permissions.add(
        Permission.objects.get(codename="add_entry")
    )
    assert entry.can_view(user_with_add_perm) is False
    assert entry.can_edit(user_with_add_perm) is False
    assert entry.can_delete(user_with_add_perm) is False
    assert entry.can_approve(user_with_add_perm) is False

    user_with_change_perm = baker.make("users.User")
    user_with_change_perm.user_permissions.add(
        Permission.objects.get(codename="change_entry")
    )
    assert entry.can_view(user_with_change_perm) is False
    assert entry.can_edit(user_with_change_perm) is True
    assert entry.can_delete(user_with_change_perm) is False
    assert entry.can_approve(user_with_change_perm) is True

    user_with_delete_perm = baker.make("users.User")
    user_with_delete_perm.user_permissions.add(
        Permission.objects.get(codename="delete_entry")
    )
    assert entry.can_view(user_with_delete_perm) is False
    assert entry.can_edit(user_with_delete_perm) is False
    assert entry.can_delete(user_with_delete_perm) is True
    assert entry.can_approve(user_with_delete_perm) is False

    user_with_view_perm = baker.make("users.User")
    user_with_view_perm.user_permissions.add(
        Permission.objects.get(codename="view_entry")
    )
    assert entry.can_view(user_with_view_perm) is True
    assert entry.can_edit(user_with_view_perm) is False
    assert entry.can_delete(user_with_view_perm) is False
    assert entry.can_approve(user_with_view_perm) is False


def test_approved_entry_permissions_other_users(make_entry):
    entry = make_entry(approved=True)
    assert entry.can_view(None) is True
    assert entry.can_edit(None) is False
    assert entry.can_delete(None) is False
    assert entry.can_approve(None) is False

    regular_user = baker.make("users.User")
    assert entry.can_view(regular_user) is True
    assert entry.can_edit(regular_user) is False
    assert entry.can_delete(regular_user) is False
    assert entry.can_approve(regular_user) is False

    superuser = baker.make("users.User", is_superuser=True)
    assert entry.can_view(superuser) is True
    assert entry.can_edit(superuser) is True
    assert entry.can_delete(superuser) is True
    assert entry.can_approve(superuser) is True

    user_with_add_perm = baker.make("users.User")
    user_with_add_perm.user_permissions.add(
        Permission.objects.get(codename="add_entry")
    )
    assert entry.can_view(user_with_add_perm) is True
    assert entry.can_edit(user_with_add_perm) is False
    assert entry.can_delete(user_with_add_perm) is False
    assert entry.can_approve(user_with_add_perm) is False

    user_with_change_perm = baker.make("users.User")
    user_with_change_perm.user_permissions.add(
        Permission.objects.get(codename="change_entry")
    )
    assert entry.can_view(user_with_change_perm) is True
    assert entry.can_edit(user_with_change_perm) is True
    assert entry.can_delete(user_with_change_perm) is False
    assert entry.can_approve(user_with_change_perm) is True

    user_with_delete_perm = baker.make("users.User")
    user_with_delete_perm.user_permissions.add(
        Permission.objects.get(codename="delete_entry")
    )
    assert entry.can_view(user_with_delete_perm) is True
    assert entry.can_edit(user_with_delete_perm) is False
    assert entry.can_delete(user_with_delete_perm) is True
    assert entry.can_approve(user_with_delete_perm) is False

    user_with_view_perm = baker.make("users.User")
    user_with_view_perm.user_permissions.add(
        Permission.objects.get(codename="view_entry")
    )
    assert entry.can_view(user_with_view_perm) is True
    assert entry.can_edit(user_with_view_perm) is False
    assert entry.can_delete(user_with_view_perm) is False
    assert entry.can_approve(user_with_view_perm) is False


def test_entry_author_needs_moderation_basic(make_entry):
    entry = make_entry()
    assert entry.author_needs_moderation() is True


def test_entry_author_needs_moderation_can_approve(make_entry):
    user_with_change_perm = baker.make("users.User")
    user_with_change_perm.user_permissions.add(
        Permission.objects.get(codename="change_entry")
    )
    entry = make_entry(author=user_with_change_perm)
    assert entry.author_needs_moderation() is False


def test_entry_author_needs_moderation_allowlist(make_entry, settings):
    user = baker.make("users.User")
    entry = make_entry(author=user)

    settings.NEWS_MODERATION_ALLOWLIST = []
    assert entry.author_needs_moderation() is True

    settings.NEWS_MODERATION_ALLOWLIST = [user.email]
    assert entry.author_needs_moderation() is False

    settings.NEWS_MODERATION_ALLOWLIST = [user.pk]
    assert entry.author_needs_moderation() is False


def test_entry_manager_custom_queryset(make_entry):
    entry_published = make_entry(approved=True, published=True)
    entry_approved = make_entry(approved=True, published=False)
    entry_not_approved = make_entry(approved=False)
    entry_not_published = make_entry(approved=False, published=False)

    assert list(Entry.objects.filter(approved=True).order_by("id")) == [
        entry_published,
        entry_approved,
    ]
    assert list(Entry.objects.filter(approved=False).order_by("id")) == [
        entry_not_approved,
        entry_not_published,
    ]
    assert list(Entry.objects.filter(published=True).order_by("id")) == [
        entry_published
    ]
    assert list(Entry.objects.filter(published=False).order_by("id")) == [
        entry_approved,
        entry_not_approved,
        entry_not_published,
    ]


def test_blogpost():
    blogpost = baker.make("BlogPost")
    assert isinstance(blogpost, Entry)
    assert blogpost.news_type == "blogpost"
    assert Entry.objects.get(id=blogpost.id).blogpost == blogpost


def test_link():
    link = baker.make("Link")
    assert isinstance(link, Entry)
    assert link.news_type == "link"
    assert Entry.objects.get(id=link.id).link == link


def test_news():
    news = baker.make("News")
    assert isinstance(news, Entry)
    assert news.news_type == "news"
    assert Entry.objects.get(id=news.id).news == news


def test_video():
    video = baker.make("Video")
    assert isinstance(video, Entry)
    assert video.news_type == "video"
    assert Entry.objects.get(id=video.id).video == video


def test_poll():
    poll = baker.make("Poll")
    assert isinstance(poll, Entry)
    assert poll.news_type == "poll"
    assert Entry.objects.get(id=poll.id).poll == poll


def test_poll_choice():
    choice = baker.make("PollChoice")
    assert isinstance(choice.poll, Poll)
