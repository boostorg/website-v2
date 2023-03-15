import pytest

from model_bakery import baker

from django.contrib.auth import get_user_model

User = get_user_model()


def test_regular_user(user):
    assert user.is_active is True
    assert user.is_staff is False
    assert user.is_superuser is False


def test_staff_user(staff_user):
    assert staff_user.is_active is True
    assert staff_user.is_staff is True
    assert staff_user.is_superuser is False


def test_super_user(super_user):
    assert super_user.is_active is True
    assert super_user.is_staff is True
    assert super_user.is_superuser is True


@pytest.mark.skip("Add this test when I have the patience for mocks")
def test_user_save_image_from_github(user):
    """
    Test `User.save_image_from_github(avatar_url)`
    See test_signals -- you will need to do something similar here, but
    dealing with a File object might make it trickier.
    """
    pass


def test_find_user(user):
    # Test finding the user by email
    assert User.objects.find_user(email=user.email) == user

    # Test finding the user by first and last name
    assert (
        User.objects.find_user(first_name=user.first_name, last_name=user.last_name)
        == user
    )

    # Test when no user is found
    assert User.objects.find_user(first_name="Jane", last_name="Smith") is None

    # Test when multiple users are found
    baker.make("users.User", first_name=user.first_name, last_name=user.last_name)
    assert (
        User.objects.find_user(first_name=user.first_name, last_name=user.last_name)
        is None
    )
