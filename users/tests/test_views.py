import pytest
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile

from allauth.account.forms import ChangePasswordForm
from PIL import Image

from ..forms import PreferencesForm, UserProfilePhotoForm
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


@pytest.mark.django_db
def test_new_current_user_profile_not_authenticated(tp, user):
    tp.assertLoginRequired("profile-account-new")


@pytest.mark.django_db
def test_new_current_user_profile_view_get(user, tp):
    with tp.login(user):
        response = tp.assertGoodView(tp.reverse("profile-account-new"), verbose=True)
        assert isinstance(response.context["change_password_form"], ChangePasswordForm)
        assert isinstance(response.context["profile_photo_form"], UserProfilePhotoForm)
        assert isinstance(response.context["profile_preferences_form"], PreferencesForm)


@pytest.mark.django_db
def test_new_current_user_profile_view_post_valid_password(user, tp):
    with tp.login(user):
        response = tp.post(
            tp.reverse("profile-account-new"),
            data={
                "email": user.email,
                "oldpassword": "password",
                "password1": "new_password",
                "password2": "new_password",
            },
            follow=True,
        )
        assert response.status_code == 200
        user.refresh_from_db()
        user.check_password("new_password")


@pytest.mark.django_db
def test_new_current_user_profile_view_post_invalid_password(user, tp):
    old_password = "password"
    with tp.login(user):
        response = tp.post(
            tp.reverse("profile-account-new"),
            data={
                "email": user.email,
                "oldpassword": "not the right password",
                "password1": "new_password",
                "password2": "new_password",
            },
            follow=True,
        )
        assert response.status_code == 200
        user.refresh_from_db()
        user.check_password(old_password)


@pytest.mark.django_db
def test_new_current_user_profile_view_post_valid_photo(user, tp):
    """Test that a user can upload a new profile picture."""
    # Create a temporary image file for testing
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp_image:
        image = Image.new("RGB", (200, 200))
        image.save(temp_image, "jpeg")
        temp_image.seek(0)

        # Wrap temp_image in Django's File object
        uploaded_file = SimpleUploadedFile(
            name="test_image.jpg", content=temp_image.read(), content_type="image/jpeg"
        )

    with tp.login(user):
        response = tp.post(
            tp.reverse("profile-account-new"),
            data={
                "image": uploaded_file,
            },
            follow=True,
        )
        assert response.status_code == 200
        user.refresh_from_db()
        assert user.image
        # confirm that password was not changed, as these are on the same screen
        assert user.check_password("password")


@pytest.mark.django_db
@pytest.mark.parametrize("user_type", ["user", "moderator_user"])
@pytest.mark.parametrize("form_field", PreferencesForm.Meta.fields)
def test_new_current_user_profile_view_post_valid_preferences(
    user_type, form_field, tp, request, assert_messages
):
    user = request.getfixturevalue(user_type)
    original_preferences = {
        field: getattr(user.preferences, field) for field in PreferencesForm.Meta.fields
    }
    new_preferences = {
        field: [] for field in PreferencesForm.Meta.fields
    }  # Clear all options

    with tp.login(user):
        response = tp.post(
            tp.reverse("profile-account-new"),
            data={**new_preferences, "update_preferences": "Update Preeferences"},
            follow=True,
        )

    assert response.status_code == 200
    user.refresh_from_db()
    for field in PreferencesForm.Meta.fields:
        if (
            field == "allow_notification_others_news_needs_moderation"
            and user_type != "moderator_user"
        ):
            assert (
                getattr(user.preferences, field) == original_preferences[field]
            )  # Field should be unchanged for non-moderators
        else:
            assert getattr(user.preferences, field) == []  # Field should be cleared

    assert_messages(
        response, [("success", "Your preferences were successfully updated.")]
    )
