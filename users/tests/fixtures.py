import pytest

from django.utils import timezone

from model_bakery import baker


@pytest.fixture
def user(db):
    """Regular website user"""
    user = baker.make(
        "users.User",
        email="user@example.com",
        first_name="Regular",
        last_name="User",
        last_login=timezone.now(),
    )
    user.set_password("password")
    user.save()

    return user


@pytest.fixture
def staff_user(db):
    """Staff website user with access to the Django admin"""
    user = baker.make(
        "users.User",
        email="staff@example.com",
        first_name="Staff",
        last_name="User",
        last_login=timezone.now(),
        is_staff=True,
    )
    user.set_password("password")
    user.save()

    return user


@pytest.fixture
def super_user(db):
    """Superuser with access to everything"""
    user = baker.make(
        "users.User",
        email="super@example.com",
        first_name="Super",
        last_name="User",
        last_login=timezone.now(),
        is_staff=True,
        is_superuser=True,
    )
    user.set_password("password")
    user.save()

    return user
