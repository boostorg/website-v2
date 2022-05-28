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
