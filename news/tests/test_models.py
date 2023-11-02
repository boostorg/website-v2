import datetime

import pytest
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.utils.timezone import now
from model_bakery import baker

from ..models import NEWS_MODELS, Entry, Poll


def test_entry_basic():
    entry = baker.make("Entry")
    assert str(entry) == entry.title
    assert entry.news_type == ""


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


def test_entry_model_image_validator(tp):
    """
    Test that the `image` field only accepts certain file types.
    """
    author = baker.make("users.User")
    entry = Entry.objects.create(title="😀 Foo Bar Baz!@! +", author=author)
    # Valid image file
    valid_image = SimpleUploadedFile(
        "test.jpg", b"file_content", content_type="image/jpeg"
    )
    entry.image = valid_image
    # This should not raise any errors
    entry.full_clean()

    # Invalid image file
    invalid_image = SimpleUploadedFile(
        "test.pdf", b"file_content", content_type="application/pdf"
    )
    entry.image = invalid_image
    # This should raise a ValidationError
    with pytest.raises(ValidationError):
        entry.full_clean()


def test_entry_model_image_file_size(tp):
    """
    Test that the `image` field rejects files larger than a specific size.
    """
    author = baker.make("users.User")
    entry = Entry.objects.create(title="😀 Foo Bar Baz!@! +", author=author)

    valid_image = SimpleUploadedFile(
        "test.jpg", b"a" * (1 * 1024 * 1024 - 1), content_type="image/jpeg"
    )
    entry.image = valid_image
    # This should not raise any errors
    entry.full_clean()

    # This should fail (just over 1MB)
    invalid_image = SimpleUploadedFile(
        "too_large.jpg", b"a" * (1 * 1024 * 1024 + 1), content_type="image/jpeg"
    )
    entry.image = invalid_image
    # This should raise a ValidationError for file size
    with pytest.raises(ValidationError):
        entry.full_clean()


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


@pytest.mark.parametrize("model_class", [Entry] + NEWS_MODELS)
def test_entry_manager_custom_queryset(make_entry, model_class):
    entry_published = make_entry(model_class, approved=True, published=True)
    entry_approved = make_entry(model_class, approved=True, published=False)
    entry_not_approved = make_entry(model_class, approved=False)
    entry_not_published = make_entry(model_class, approved=False, published=False)

    assert list(model_class.objects.filter(approved=True).order_by("id")) == [
        entry_published,
        entry_approved,
    ]
    assert list(model_class.objects.filter(approved=False).order_by("id")) == [
        entry_not_approved,
        entry_not_published,
    ]
    assert list(model_class.objects.filter(published=True).order_by("id")) == [
        entry_published
    ]
    assert list(model_class.objects.filter(published=False).order_by("id")) == [
        entry_approved,
        entry_not_approved,
        entry_not_published,
    ]
    # Intentionally query via Entry since children do not have the annotation
    assert {e.tag for e in Entry.objects.all()} == {model_class.news_type}


def test_entry_manager_custom_queryset_tags_mixed(make_entry):
    for model_class in [Entry] + NEWS_MODELS:
        make_entry(model_class)

    entries = Entry.objects.all().order_by("id")
    assert [e.tag for e in entries] == ["", "blogpost", "link", "news", "poll", "video"]


def test_entry_manager_published(make_entry):
    entry_published = make_entry(Entry, approved=True, published=True)
    # Check that unpublished, approved entries are not returned
    make_entry(Entry, approved=True, published=False)
    # Check that unapproved entries are not returned
    make_entry(Entry, approved=False)
    # Check that unpublished entries are not returned
    make_entry(Entry, approved=False, published=False)
    assert list(Entry.objects.published()) == [entry_published]


def test_blogpost():
    blogpost = baker.make("BlogPost")
    assert isinstance(blogpost, Entry)
    assert blogpost.news_type == "blogpost"
    entry = Entry.objects.get(id=blogpost.id)
    assert entry.blogpost == blogpost
    assert entry.tag == "blogpost"


def test_link():
    link = baker.make("Link")
    assert isinstance(link, Entry)
    assert link.news_type == "link"
    entry = Entry.objects.get(id=link.id)
    assert entry.link == link
    assert entry.tag == "link"


def test_news():
    news = baker.make("News")
    assert isinstance(news, Entry)
    assert news.news_type == "news"
    entry = Entry.objects.get(id=news.id)
    assert entry.news == news
    assert entry.tag == "news"


def test_video():
    video = baker.make("Video")
    assert isinstance(video, Entry)
    assert video.news_type == "video"
    entry = Entry.objects.get(id=video.id)
    assert entry.video == video
    assert entry.tag == "video"


def test_poll():
    poll = baker.make("Poll")
    assert isinstance(poll, Entry)
    assert poll.news_type == "poll"
    entry = Entry.objects.get(id=poll.id)
    assert entry.poll == poll
    assert entry.tag == "poll"


def test_poll_choice():
    choice = baker.make("PollChoice")
    assert isinstance(choice.poll, Poll)
