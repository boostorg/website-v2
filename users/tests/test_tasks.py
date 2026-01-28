import pytest
from datetime import timedelta
from unittest.mock import patch

from model_bakery import baker
from allauth.account.models import EmailAddress

from ..tasks import (
    UserMissingGithubUsername,
    update_user_github_photo,
    remove_unverified_users,
)
from ..constants import UNVERIFIED_CLEANUP_DAYS, UNVERIFIED_CLEANUP_BEGIN


@pytest.fixture
def mock_current_time():
    """Current time set well after cleanup begin + grace period."""
    return UNVERIFIED_CLEANUP_BEGIN + timedelta(days=30)


@pytest.fixture
def mocked_now(mock_current_time):
    """Mock timezone.now() to return mock_current_time automatically."""
    with patch("users.tasks.timezone.now") as mock_now:
        mock_now.return_value = mock_current_time
        yield mock_now


@pytest.fixture
def old_date_after_cleanup_begin(mock_current_time):
    """Date just after cleanup begin, old enough to be deleted."""
    return UNVERIFIED_CLEANUP_BEGIN + timedelta(days=1)


@pytest.fixture
def old_date_before_cleanup_begin():
    """Date before cleanup begin - users from this date should not be deleted."""
    return UNVERIFIED_CLEANUP_BEGIN - timedelta(days=1)


@pytest.fixture
def recent_date(mock_current_time):
    """Recent date - users from this date should not be deleted due to age."""
    return mock_current_time - timedelta(days=UNVERIFIED_CLEANUP_DAYS - 1)


@pytest.fixture
def old_date(mock_current_time):
    """Old date - users from this date should be deleted if they meet other criteria."""
    return mock_current_time - timedelta(days=UNVERIFIED_CLEANUP_DAYS + 1)


def test_update_user_github_photo_user_not_found(db):
    with pytest.raises(Exception):
        update_user_github_photo(9999)


def test_update_user_github_photo_no_gh_username(user):
    user.github_username = ""
    user.save()
    with pytest.raises(UserMissingGithubUsername):
        update_user_github_photo(user.pk)


@pytest.mark.django_db
def test_removes_unverified_users_older_than_cleanup_days(
    mocked_now, old_date_after_cleanup_begin
):
    """Test that unverified users older than UNVERIFIED_CLEANUP_DAYS are removed."""
    # Create a user that should be deleted (unverified, old enough, after cleanup begin date)
    user_to_delete = baker.make(
        "users.User",
        email="old_unverified@example.com",
        claimed=True,
        date_joined=old_date_after_cleanup_begin,
    )
    # Create unverified email address for this user
    EmailAddress.objects.create(
        user=user_to_delete, email=user_to_delete.email, verified=False, primary=True
    )

    remove_unverified_users()
    from users.models import User

    assert not User.objects.filter(id=user_to_delete.id).exists()


@pytest.mark.django_db
def test_keeps_unverified_users_newer_than_cleanup_days(mocked_now, recent_date):
    """Test that unverified users newer than UNVERIFIED_CLEANUP_DAYS are kept."""
    # Create a user that should NOT be deleted (unverified but too new)
    user_to_keep = baker.make(
        "users.User",
        email="recent_unverified@example.com",
        claimed=True,
        date_joined=recent_date,
    )
    # Create unverified email address for this user
    EmailAddress.objects.create(
        user=user_to_keep, email=user_to_keep.email, verified=False, primary=True
    )

    remove_unverified_users()
    from users.models import User

    assert User.objects.filter(id=user_to_keep.id).exists()


@pytest.mark.django_db
def test_keeps_verified_users(mocked_now, old_date):
    """Test that verified users are not deleted regardless of age."""
    # Create an old user with verified email
    verified_user = baker.make(
        "users.User",
        email="verified@example.com",
        claimed=True,
        date_joined=old_date,
    )
    # Create verified email address for this user
    EmailAddress.objects.create(
        user=verified_user, email=verified_user.email, verified=True, primary=True
    )

    remove_unverified_users()
    from users.models import User

    assert User.objects.filter(id=verified_user.id).exists()


@pytest.mark.django_db
def test_keeps_unclaimed_users(mocked_now, old_date):
    """Test that unclaimed users are not deleted."""
    # Create an old unclaimed user with unverified email
    unclaimed_user = baker.make(
        "users.User",
        email="unclaimed@example.com",
        claimed=False,
        date_joined=old_date,
    )
    # Create unverified email address for this user
    EmailAddress.objects.create(
        user=unclaimed_user, email=unclaimed_user.email, verified=False, primary=True
    )

    remove_unverified_users()
    from users.models import User

    assert User.objects.filter(id=unclaimed_user.id).exists()


@pytest.mark.django_db
def test_keeps_users_joined_before_cleanup_begin_date(old_date_before_cleanup_begin):
    """Test that users who joined before UNVERIFIED_CLEANUP_BEGIN are not deleted."""
    # Create an old user who joined before the cleanup begin date
    old_user = baker.make(
        "users.User",
        email="before_cleanup@example.com",
        claimed=True,
        date_joined=old_date_before_cleanup_begin,
    )
    # Create unverified email address for this user
    EmailAddress.objects.create(
        user=old_user, email=old_user.email, verified=False, primary=True
    )

    remove_unverified_users()
    from users.models import User

    assert User.objects.filter(id=old_user.id).exists()


@pytest.mark.django_db
def test_handles_multiple_users(mocked_now, old_date_after_cleanup_begin, recent_date):
    """Test that the task handles multiple users correctly."""
    from users.models import User

    # User to delete: old, claimed, unverified, after cleanup begin
    user_to_delete1 = baker.make(
        "users.User",
        email="delete1@example.com",
        claimed=True,
        date_joined=old_date_after_cleanup_begin,
    )
    EmailAddress.objects.create(
        user=user_to_delete1, email=user_to_delete1.email, verified=False, primary=True
    )

    # Another user to delete
    user_to_delete2 = baker.make(
        "users.User",
        email="delete2@example.com",
        claimed=True,
        date_joined=old_date_after_cleanup_begin,
    )
    EmailAddress.objects.create(
        user=user_to_delete2, email=user_to_delete2.email, verified=False, primary=True
    )

    # User to keep: too recent
    user_to_keep1 = baker.make(
        "users.User",
        email="keep1@example.com",
        claimed=True,
        date_joined=recent_date,
    )
    EmailAddress.objects.create(
        user=user_to_keep1, email=user_to_keep1.email, verified=False, primary=True
    )

    # User to keep: verified
    user_to_keep2 = baker.make(
        "users.User",
        email="keep2@example.com",
        claimed=True,
        date_joined=old_date_after_cleanup_begin,
    )
    EmailAddress.objects.create(
        user=user_to_keep2, email=user_to_keep2.email, verified=True, primary=True
    )

    initial_count = User.objects.count()
    remove_unverified_users()
    assert not User.objects.filter(id=user_to_delete1.id).exists()
    assert not User.objects.filter(id=user_to_delete2.id).exists()
    assert User.objects.filter(id=user_to_keep1.id).exists()
    assert User.objects.filter(id=user_to_keep2.id).exists()
    assert User.objects.count() == initial_count - 2


@pytest.mark.django_db
def test_handles_no_users_to_delete(mocked_now, recent_date):
    """Test that the task handles the case where no users need to be deleted."""
    from users.models import User

    # Create a user that should NOT be deleted (recent)
    test_user = baker.make(
        "users.User",
        email="recent@example.com",
        claimed=True,
        date_joined=recent_date,
    )
    EmailAddress.objects.create(
        user=test_user, email=test_user.email, verified=False, primary=True
    )

    initial_count = User.objects.count()
    remove_unverified_users()
    assert User.objects.count() == initial_count
    assert User.objects.filter(id=test_user.id).exists()


@pytest.mark.django_db
@patch("users.tasks.logger")
def test_remove_unverified_users_logging(
    mock_logger, mocked_now, old_date_after_cleanup_begin
):
    """Test that the task logs appropriately."""
    # Create a user to delete
    user_to_delete = baker.make(
        "users.User",
        email="logging_test@example.com",
        claimed=True,
        date_joined=old_date_after_cleanup_begin,
    )
    EmailAddress.objects.create(
        user=user_to_delete, email=user_to_delete.email, verified=False, primary=True
    )

    remove_unverified_users()
    mock_logger.info.assert_any_call("Starting remove_unverified_users task")
    mock_logger.info.assert_any_call("Found 1 unverified users for deletion")
    mock_logger.info.assert_any_call("Successfully processed 1 unverified users")


@patch("users.tasks.logger")
def test_remove_unverified_users_exception_handling(mock_logger):
    """Test that exceptions are properly caught and logged."""
    # Mock User.objects.filter to raise an exception
    with patch("users.tasks.User.objects.filter") as mock_filter:
        mock_filter.side_effect = Exception("Test exception")

        # Run the task - should not raise the exception
        remove_unverified_users()
        # Verify exception was logged
        mock_logger.exception.assert_called_once_with(
            "Error occurred processing unverified users for removal: Test exception"
        )
