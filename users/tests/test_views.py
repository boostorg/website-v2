import pytest
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile

from allauth.account.forms import ChangePasswordForm
from PIL import Image

from ..forms import PreferencesForm, UserProfilePhotoForm


@pytest.mark.django_db
def test_current_user_profile_not_authenticated(tp, user):
    tp.assertLoginRequired("profile-account")


@pytest.mark.django_db
def test_current_user_profile_view_get(user, tp):
    with tp.login(user):
        response = tp.assertGoodView(tp.reverse("profile-account"), verbose=True)
        assert isinstance(response.context["change_password_form"], ChangePasswordForm)
        assert isinstance(response.context["profile_photo_form"], UserProfilePhotoForm)
        assert isinstance(response.context["profile_preferences_form"], PreferencesForm)


@pytest.mark.django_db
def test_current_user_profile_view_post_valid_password(user, tp):
    with tp.login(user):
        response = tp.post(
            tp.reverse("profile-account"),
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
def test_current_user_profile_view_post_invalid_password(user, tp):
    old_password = "password"
    with tp.login(user):
        response = tp.post(
            tp.reverse("profile-account"),
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
def test_current_user_profile_view_update_name(user, tp):
    new_first_name = "Tester"
    new_last_name = "Testerson"

    with tp.login(user):
        response = tp.post(
            tp.reverse("profile-account"),
            data={
                "email": user.email,
                "first_name": new_first_name,
                "last_name": new_last_name,
                "update_profile": "",
            },
            follow=True,
        )
        assert response.status_code == 200
        user.refresh_from_db()
        assert user.first_name == new_first_name
        assert user.last_name == new_last_name


@pytest.mark.django_db
def test_current_user_profile_view_post_valid_photo(user, tp):
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
            tp.reverse("profile-account"),
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
def test_current_user_profile_view_post_valid_preferences(
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
            tp.reverse("profile-account"),
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
