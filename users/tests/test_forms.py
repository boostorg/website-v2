import pytest

from ..forms import PreferencesForm
from ..models import Preferences
from news.models import NEWS_MODELS


def test_preferences_form_fields_no_user():
    form = PreferencesForm()
    assert sorted(form.fields.keys()) == [
        "allow_notification_others_news_posted",
        "allow_notification_own_news_approved",
    ]
    all_news = sorted(m.news_type for m in NEWS_MODELS)
    assert form.initial == {
        "allow_notification_others_news_posted": all_news,
        "allow_notification_own_news_approved": all_news,
    }


def test_preferences_form_fields_regular_user(user):
    instance = user.preferences
    form = PreferencesForm(instance=user.preferences)
    assert sorted(form.fields.keys()) == [
        "allow_notification_others_news_posted",
        "allow_notification_own_news_approved",
    ]
    assert form.initial == {i: getattr(instance, i) for i in form.fields}


def test_preferences_form_fields_moderator_user(moderator_user):
    instance = moderator_user.preferences
    form = PreferencesForm(instance=moderator_user.preferences)
    assert sorted(form.fields.keys()) == [
        "allow_notification_others_news_needs_moderation",
        "allow_notification_others_news_posted",
        "allow_notification_own_news_approved",
    ]
    assert form.initial == {i: getattr(instance, i) for i in form.fields}


@pytest.mark.parametrize("form_field", PreferencesForm.Meta.fields)
@pytest.mark.parametrize("model_class", NEWS_MODELS)
def test_preferences_form_model_modifies_instance_empty_list_no_moderator(
    user, form_field, model_class
):
    original = Preferences.ALL_NEWS_TYPES
    setattr(user.preferences, form_field, original)
    expected = []
    form = PreferencesForm(instance=user.preferences, data={form_field: expected})
    assert form.is_valid(), form.errors

    result = form.save()

    # Since the user is not moderator, the value for
    # allow_notification_others_news_needs_moderation should not change.
    if form_field == "allow_notification_others_news_needs_moderation":
        expected = original
    assert getattr(result, form_field) == expected
    user.refresh_from_db()
    assert getattr(user.preferences, form_field) == expected

    # Now, set a single item.
    expected = [model_class.news_type]
    form = PreferencesForm(instance=user.preferences, data={form_field: expected})
    assert form.is_valid(), form.errors

    result = form.save()

    # Since the user is not moderator, the value for
    # allow_notification_others_news_needs_moderation should not change.
    if form_field == "allow_notification_others_news_needs_moderation":
        expected = original
    assert getattr(result, form_field) == expected
    user.refresh_from_db()
    assert getattr(user.preferences, form_field) == expected


@pytest.mark.parametrize("form_field", PreferencesForm.Meta.fields)
@pytest.mark.parametrize("model_class", NEWS_MODELS)
def test_preferences_form_model_modifies_instance_empty_list_user_moderator(
    moderator_user, form_field, model_class
):
    setattr(moderator_user.preferences, form_field, Preferences.ALL_NEWS_TYPES)
    expected = []
    form = PreferencesForm(
        instance=moderator_user.preferences, data={form_field: expected}
    )
    assert form.is_valid(), form.errors

    result = form.save()

    assert getattr(result, form_field) == expected
    moderator_user.refresh_from_db()
    assert getattr(moderator_user.preferences, form_field) == expected

    # Now, set a single item.
    expected = [model_class.news_type]
    form = PreferencesForm(
        instance=moderator_user.preferences, data={form_field: expected}
    )
    assert form.is_valid(), form.errors

    result = form.save()

    assert getattr(result, form_field) == expected
    moderator_user.refresh_from_db()
    assert getattr(moderator_user.preferences, form_field) == expected
