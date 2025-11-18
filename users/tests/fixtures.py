import io

from PIL import Image
import pytest
from model_bakery import baker

from django.utils import timezone


@pytest.fixture
def user(db):
    """Regular website user"""
    user = baker.make(
        "users.User",
        email="user@example.com",
        display_name="Regular User",
        indicate_last_login_method=False,
        is_commit_author_name_overridden=False,
        last_login=timezone.now(),
        image=None,
    )
    filename = "normal-user.png"
    file = io.BytesIO()
    file.name = filename
    image = Image.new("RGBA", size=(100, 100), color=(155, 0, 0))
    image.save(file, "png")
    file.seek(0)
    user.profile_image.save(filename, file)

    user.set_password("password")
    user.save()

    return user


@pytest.fixture
def staff_user(db):
    """Staff website user with access to the Django admin"""
    user = baker.make(
        "users.User",
        email="staff@example.com",
        display_name="Staff User",
        last_login=timezone.now(),
        is_staff=True,
        image=None,
    )
    filename = "staff-user.png"
    file = io.BytesIO()
    file.name = filename
    image = Image.new("RGBA", size=(100, 100), color=(155, 0, 0))
    image.save(file, "png")
    file.seek(0)
    user.profile_image.save(filename, file)

    user.set_password("password")
    user.save()

    return user


@pytest.fixture
def super_user(db):
    """Superuser with access to everything"""
    user = baker.make(
        "users.User",
        email="super@example.com",
        display_name="Super User",
        last_login=timezone.now(),
        is_staff=True,
        is_superuser=True,
        image=None,
    )
    filename = "super-user.png"
    file = io.BytesIO()
    file.name = filename
    image = Image.new("RGBA", size=(100, 100), color=(155, 0, 0))
    image.save(file, "png")
    file.seek(0)
    user.profile_image.save(filename, file)
    user.set_password("password")
    user.save()

    return user


@pytest.fixture
def assert_messages():
    def _assert_and_fetch(response, expected):
        messages = [
            (m.level_tag, m.message) for m in response.context.get("messages", [])
        ]
        assert messages == expected

    return _assert_and_fetch
