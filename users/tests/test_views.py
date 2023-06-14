import pytest

from ..forms import PreferencesForm
from ..models import Preferences


def test_preferences_user_not_authenticated(tp, user):
    tp.assertLoginRequired("profile-preferences")


@pytest.mark.parametrize("user_type", ["user", "moderator_user"])
def test_preferences_get(tp, user_type, request):
    """List preferences options for authenticated users."""
    user = request.getfixturevalue(user_type)
    with tp.login(user):
        response = tp.assertGoodView(
            tp.reverse("profile-preferences"), test_query_count=5, verbose=True
        )

    tp.assertResponseContains("Update Preferences", response)

    obj = tp.get_context("object")
    assert isinstance(obj, Preferences)
    assert obj.user == user

    form = tp.get_context("form")
    assert isinstance(form, PreferencesForm)
    assert form.instance == obj
    for field in form:
        tp.assertResponseContains(str(field), response)


@pytest.mark.parametrize("user_type", ["user", "moderator_user"])
@pytest.mark.parametrize("form_field", PreferencesForm.Meta.fields)
def test_preferences_post_clears_options(
    tp, user_type, request, form_field, assert_messages
):
    """List preferences options for authenticated users."""
    user = request.getfixturevalue(user_type)
    original = getattr(user.preferences, form_field)
    expected = []

    with tp.login(user):
        response = tp.post(
            "profile-preferences", data={form_field: expected}, follow=True
        )

    tp.assertRedirects(response, tp.reverse("profile-preferences"))
    user.refresh_from_db()
    if (
        form_field == "allow_notification_others_news_needs_moderation"
        and user_type != "moderator_user"
    ):
        expected = original
    assert getattr(user.preferences, form_field) == expected

    assert_messages(
        response, [("success", "Your preferences were successfully updated.")]
    )
