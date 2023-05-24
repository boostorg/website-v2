import datetime

from django.utils.timezone import now
from model_bakery import baker

from ..forms import BlogPostForm, EntryForm, LinkForm, PollForm, VideoForm
from ..models import Entry


def test_form_fields():
    form = EntryForm()
    assert sorted(form.fields.keys()) == ["content", "title"]


def test_form_model_creates_entry(make_entry):
    title = "The Title"
    content = "Some content"
    user = baker.make("users.User")
    assert Entry.objects.filter(title=title).count() == 0

    before = now()
    form = EntryForm(instance=None, data={"title": title, "content": content})
    assert form.is_valid()
    form.instance.author = user
    result = form.save()
    after = now()

    assert isinstance(result, Entry)
    assert result.pk is not None
    assert before <= result.created_at <= after
    assert before <= result.modified_at <= after
    assert before <= result.publish_at <= after
    assert result.approved_at is None
    assert result.title == title
    assert result.content == content
    assert result.author == user
    assert result.moderator is None
    assert result.author_needs_moderation() is True
    assert Entry.objects.get(pk=result.pk) == result


def test_form_model_modifies_entry(make_entry):
    # Guard against runs that are too fast and this modified_at would not change
    past = now() - datetime.timedelta(minutes=1)
    news = make_entry(title="Old title", modified_at=past)
    form = EntryForm(instance=news, data={"title": "New title"})
    assert form.is_valid()

    result = form.save()

    # Modified fields
    assert result.title == "New title"
    assert result.modified_at > past
    # Unchanged fields
    assert result.pk == news.pk
    assert result.created_at == news.created_at
    assert result.approved_at == news.approved_at
    assert result.publish_at == news.publish_at
    assert result.content == news.content
    assert result.author == news.author
    assert result.moderator == news.moderator
    assert result.author_needs_moderation() is True


def test_form_save_unapproved_news_author_needs_moderation(make_entry):
    entry = make_entry(approved=False)
    assert entry.author_needs_moderation() is True

    form = EntryForm(instance=entry)
    result = form.save()

    result.refresh_from_db()
    assert not entry.is_approved  # No automatic news approval.
    assert entry.author_needs_moderation() is True


def test_form_save_unapproved_news_author_does_not_need_moderation(
    make_entry, settings
):
    user = baker.make("users.User")
    settings.NEWS_MODERATION_ALLOWLIST = [user.email]
    entry = make_entry(approved=False, author=user)
    assert entry.author_needs_moderation() is False

    before = now()
    form = EntryForm(instance=entry)
    result = form.save()
    after = now()

    result.refresh_from_db()
    assert entry.is_approved  # Automatic news approval!
    assert entry.author_needs_moderation() is False
    assert before <= result.modified_at <= after
    assert before <= result.approved_at <= after
    assert result.moderator == result.author
    assert Entry.objects.get(pk=result.pk) == result


def test_form_save_approved_news(make_entry, settings):
    entry = make_entry(approved=True)
    assert entry.author_needs_moderation() is True

    form = EntryForm(instance=entry)
    result = form.save()

    result.refresh_from_db()
    assert entry.is_approved  # No entry status change.
    assert entry.author_needs_moderation() is True

    # when author can post without moderation, no double approve happens
    settings.NEWS_MODERATION_ALLOWLIST = [entry.author.email]
    assert entry.author_needs_moderation() is False

    result = form.save()
    result.refresh_from_db()
    assert entry.is_approved  # No entry status change and no exception.


def test_blogpost_form():
    form = BlogPostForm()
    assert isinstance(form, EntryForm)
    assert sorted(form.fields.keys()) == ["content", "title"]


def test_link_form():
    form = LinkForm()
    assert isinstance(form, EntryForm)
    assert sorted(form.fields.keys()) == ["external_url", "title"]


def test_poll_form():
    form = PollForm()
    assert isinstance(form, EntryForm)
    assert sorted(form.fields.keys()) == ["content", "title"]


def test_video_form():
    form = VideoForm()
    assert isinstance(form, EntryForm)
    assert sorted(form.fields.keys()) == ["external_url", "title"]
