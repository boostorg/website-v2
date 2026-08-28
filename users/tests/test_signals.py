from unittest.mock import patch

import pytest
from model_bakery import baker

from users.models import GithubActivity


@pytest.mark.skip("Reminder to write this test when I have the patience for mocks")
def test_import_social_profile_data():
    """
    TODO:
    - Test users.signals.import_social_profile_data
    - Set `SocialAccount.extra_data` to the github_api_get_user_by_username_response
      fixture in the libraries app -- it's not identical but it has what you need
    - You probably need to use `responses` and not `patch`
    """
    pass


def _connect(user, provider, login="testuser"):
    return baker.make(
        "socialaccount.SocialAccount",
        user=user,
        provider=provider,
        extra_data={"login": login, "name": "Test User"},
    )


def test_github_connect_queues_activity_refresh(
    user, db, django_capture_on_commit_callbacks
):
    """Linking GitHub kicks an initial fetch without waiting for a page load."""
    with patch("users.tasks.refresh_github_activity.delay") as delay:
        with django_capture_on_commit_callbacks(execute=True):
            _connect(user, "github")

    delay.assert_called_once_with(user.pk)


def test_github_connect_refresh_runs_after_username_is_saved(
    user, db, django_capture_on_commit_callbacks
):
    """The task must not fire before the github_username hits the database."""
    seen = {}

    def capture(user_pk):
        from users.models import User

        seen["username"] = User.objects.get(pk=user_pk).github_username

    with patch("users.tasks.refresh_github_activity.delay", side_effect=capture):
        with django_capture_on_commit_callbacks(execute=True):
            _connect(user, "github", login="octocat")

    assert seen["username"] == "octocat"


def test_google_connect_does_not_queue_activity_refresh(
    user, db, django_capture_on_commit_callbacks
):
    with patch("users.tasks.refresh_github_activity.delay") as delay:
        with django_capture_on_commit_callbacks(execute=True):
            _connect(user, "google")

    delay.assert_not_called()


def test_github_disconnect_deletes_stored_activity(user, db):
    account = _connect(user, "github")
    GithubActivity.upsert_for_user(user, {"total_commits": 5})
    assert GithubActivity.objects.filter(user=user).exists()

    account.delete()

    assert not GithubActivity.objects.filter(user=user).exists()


def test_google_disconnect_keeps_github_activity(user, db):
    account = _connect(user, "google")
    GithubActivity.upsert_for_user(user, {"total_commits": 5})

    account.delete()

    assert GithubActivity.objects.filter(user=user).exists()


def _connect_with(user, provider, extra_data):
    return baker.make(
        "socialaccount.SocialAccount",
        user=user,
        provider=provider,
        extra_data=extra_data,
    )


def test_connect_keeps_a_display_name_the_user_chose(user, db):
    """Linking GitHub must not overwrite a name the user set themselves."""
    user.display_name = "Alice Chen"
    user.save()

    _connect_with(user, "github", {"login": "achen92", "name": "achen92"})
    user.refresh_from_db()

    assert user.display_name == "Alice Chen"


def test_connect_fills_a_blank_display_name_from_github_name(user, db):
    user.display_name = ""
    user.save()

    _connect_with(user, "github", {"login": "achen92", "name": "Alice Chen"})
    user.refresh_from_db()

    assert user.display_name == "Alice Chen"


def test_connect_falls_back_to_the_github_handle(user, db):
    """GitHub's name is optional, so a null must not blank the display name."""
    user.display_name = ""
    user.save()

    _connect_with(user, "github", {"login": "achen92", "name": None})
    user.refresh_from_db()

    assert user.display_name == "achen92"


def test_google_connect_keeps_a_display_name_the_user_chose(user, db):
    user.display_name = "Alice Chen"
    user.save()

    _connect_with(user, "google", {"name": "A. Chen", "picture": ""})
    user.refresh_from_db()

    assert user.display_name == "Alice Chen"


def test_google_connect_fills_a_blank_display_name(user, db):
    user.display_name = ""
    user.save()

    _connect_with(user, "google", {"name": "A. Chen", "picture": ""})
    user.refresh_from_db()

    assert user.display_name == "A. Chen"
