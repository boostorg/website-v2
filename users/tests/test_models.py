import pytest

from test_plus import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


def test_regular_user(user):
    assert user.is_active == True
    assert user.is_staff == False
    assert user.is_superuser == False


def test_staff_user(staff_user):
    assert staff_user.is_active == True
    assert staff_user.is_staff == True
    assert staff_user.is_superuser == False


def test_super_user(super_user):
    assert super_user.is_active == True
    assert super_user.is_staff == True
    assert super_user.is_superuser == True


@pytest.mark.skip("Add this test when I have the patience for mocks")
def test_user_save_image_from_github(user):
    """
    Test `User.save_image_from_github(avatar_url)`
    See test_signals -- you will need to do something similar here, but
    dealing with a File object might make it trickier.
    """
    pass
