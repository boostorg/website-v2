import io
import pytest

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.images import ImageFile
from PIL import Image


from ..forms import (
    CustomResetPasswordFromKeyForm,
    PreferencesForm,
    UserProfileForm,
    UserProfilePhotoForm,
)
from ..models import Preferences
from news.models import NEWS_MODELS


def test_custom_reset_password_form(user):
    user.claimed = False
    user.save()
    user.refresh_from_db()

    reset_key = "your_reset_key"
    form = CustomResetPasswordFromKeyForm(
        data={
            "key": reset_key,
            "email": user.email,
            "password1": "new_password",
            "password2": "new_password",
        },
        user=user,
    )
    assert form.is_valid()
    form.save()
    user.refresh_from_db()
    assert user.claimed is True


def test_preferences_form_fields_no_user():
    form = PreferencesForm()
    assert sorted(form.fields.keys()) == [
        "allow_notification_others_news_posted",
        "allow_notification_own_news_approved",
        "allow_notification_terms_changed",
    ]
    all_news = sorted(m.news_type for m in NEWS_MODELS)
    assert form.initial == {
        "allow_notification_others_news_posted": all_news,
        "allow_notification_own_news_approved": all_news,
        "allow_notification_terms_changed": False,
    }


def test_preferences_form_fields_regular_user(user):
    instance = user.preferences
    form = PreferencesForm(instance=user.preferences)
    assert sorted(form.fields.keys()) == [
        "allow_notification_others_news_posted",
        "allow_notification_own_news_approved",
        "allow_notification_terms_changed",
    ]
    assert form.initial == {i: getattr(instance, i) for i in form.fields}


def test_preferences_form_fields_moderator_user(moderator_user):
    instance = moderator_user.preferences
    form = PreferencesForm(instance=moderator_user.preferences)
    assert sorted(form.fields.keys()) == [
        "allow_notification_others_news_needs_moderation",
        "allow_notification_others_news_posted",
        "allow_notification_own_news_approved",
        "allow_notification_terms_changed",
    ]
    assert form.initial == {i: getattr(instance, i) for i in form.fields}


@pytest.mark.parametrize("form_field", PreferencesForm.Meta.fields)
@pytest.mark.parametrize("model_class", NEWS_MODELS)
def test_preferences_form_model_modifies_instance_empty_list_no_moderator(
    user, form_field, model_class
):
    original = Preferences.ALL_NEWS_TYPES
    expected = []
    if form_field == "allow_notification_terms_changed":
        original = False
        expected = True
    setattr(user.preferences, form_field, original)
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

    if form_field == "allow_notification_terms_changed":
        # No further testing needed for this field
        return

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
    if form_field == "allow_notification_terms_changed":
        # this test doesn't make sense for this preference
        return
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


def test_user_profile_form(user):
    form = UserProfileForm(instance=user)
    assert set(form.fields.keys()) == {
        "display_name",
        "email",
        "indicate_last_login_method",
    }
    assert form.initial == {
        "display_name": user.display_name,
        "email": user.email,
        "indicate_last_login_method": user.indicate_last_login_method,
    }
    form = UserProfileForm(instance=user, data={"email": "test@example.com"})
    assert form.is_valid()
    form.save()
    user.refresh_from_db()
    assert user.email == "test@example.com"


def test_user_profile_photo_form_save(user):
    """
    Test that the UserProfilePhotoForm deletes the old image and saves the new one.
    """

    def create_test_image_file(filename="test.png"):
        file = io.BytesIO()
        image = Image.new("RGBA", size=(100, 100), color=(155, 0, 0))
        image.save(file, "png")
        file.name = filename
        file.seek(0)
        return file

    old_image = ImageFile(create_test_image_file(filename="initial_image.png"))
    user.image.save("initial_image.png", old_image)

    # Make sure the initial image was saved
    initial_path = user.image.path
    assert initial_path is not None

    # Create new image for upload
    new_image = SimpleUploadedFile(
        "new_image.jpeg",
        create_test_image_file(filename="new_image.jpeg").read(),
        content_type="image/jpeg",
    )

    form = UserProfilePhotoForm({"image": new_image}, instance=user)
    assert form.is_valid()
    updated_user = form.save()
    updated_user.refresh_from_db()
    assert str(user.pk) in updated_user.image.path
