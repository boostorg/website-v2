from django.utils import timezone

from users.models import User


def test_record_login_email(user):
    now = timezone.now()
    assert user.last_login < now
    User.objects.record_login(email=user.email)
    user.refresh_from_db()
    assert user.last_login > now


def test_record_login_user(user):
    now = timezone.now()
    assert user.last_login < now
    User.objects.record_login(user=user)
    user.refresh_from_db()
    assert user.last_login > now


def test_user_creation(db):
    u = User.objects.create_user("t1@example.com", "t1pass")
    assert u.is_active is True
    assert u.is_staff is False
    assert u.is_superuser is False


def test_staff_user_creation(db):
    u = User.objects.create_staffuser("t2@example.com", "t2pass")
    assert u.is_active is True
    assert u.is_staff is True
    assert u.is_superuser is False


def test_super_user_creation(db):
    u = User.objects.create_superuser("t3@example.com", "t3pass")
    assert u.is_active is True
    assert u.is_staff is True
    assert u.is_superuser is True


def test_create_stub_user(db):
    u = User.objects.create_stub_user(
        "t4@example.com",
        None,
        first_name="Tester",
        last_name="Testerson",
        valid_email=False,
    )
    assert u.claimed is False
    assert u.valid_email is False
    assert u.is_active is True
    assert u.is_staff is False
    assert u.is_superuser is False
    assert u.first_name == "Tester"
    assert u.last_name == "Testerson"
