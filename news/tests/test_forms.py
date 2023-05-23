import datetime

from django.utils.timezone import now
from model_bakery import baker

from ..forms import EntryForm
from ..models import Entry


def test_form_fields():
    form = EntryForm()
    assert sorted(form.fields.keys()) == ["description", "title"]


def test_form_model_creates_entry(make_entry):
    title = "The Title"
    description = "Some description"
    user = baker.make("users.User")
    assert Entry.objects.filter(title=title).count() == 0

    before = now()
    form = EntryForm(instance=None, data={"title": title, "description": description})
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
    assert result.description == description
    assert result.author == user
    assert result.moderator is None
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
    assert result.description == news.description
    assert result.author == news.author
    assert result.moderator == news.moderator
