import datetime
import pytest

from django.utils import timezone

from model_bakery import baker

from users.models import InvitationToken


@pytest.fixture
def user(db):
    """Regular website user"""
    user = baker.make(
        "users.User",
        email="user@example.com",
        first_name="Regular",
        last_name="User",
        last_login=timezone.now(),
        image="static/img/fpo/user.png",
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
        image="static/img/fpo/user.png",
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
        image="static/img/fpo/user.png",
    )
    user.set_password("password")
    user.save()

    return user


@pytest.fixture
def invitation_token(user):
    expiration_date = datetime.datetime.now() + datetime.timedelta(days=3)
    return baker.make(InvitationToken, user=user, expiration_date=expiration_date)