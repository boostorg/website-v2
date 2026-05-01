from datetime import datetime
from unittest.mock import MagicMock, patch
from versions.models import Version
from versions.tasks import get_release_date_for_version, skip_tag
from libraries.management.commands.release_tasks import ReleaseTasksManager

import pytest
import time


@pytest.fixture
def github_api_client():
    return MagicMock()


@pytest.mark.django_db
def test_get_release_date_for_version(version):
    """
    Test that the `get_release_date_for_version` task fetches and updates
    the release date.
    """
    commit_url = "https://api.github.com/repos/boostorg/boost/git/commits/some_sha"
    expected = datetime(2023, 1, 1).date()

    with patch(
        "core.githubhelper.GithubAPIClient.get_commit_by_sha"
    ) as mock_get_commit_by_sha:
        mock_get_commit_by_sha.return_value = {
            "committer": {"date": "2023-01-01T00:00:00Z"},
            "message": "some_message",
            "html_url": "some_url",
        }
        get_release_date_for_version(version.pk, commit_url)

    version.refresh_from_db()
    assert version.release_date == expected


def test_skip_tag(version):
    # Assert that existing tag names are skipped if new is True
    assert skip_tag(version.name, True) is True

    # Assert that existing tag names are not skipped if new is False
    assert skip_tag(version.name, False) is False

    # Assert that if it's on the exclusion list, it's skipped
    assert skip_tag("boost-beta-1.0") is True
    assert skip_tag("boost-1.25.1-bgl") is True

    # Assert that if the version is lower that the min, it's skipped
    assert skip_tag("boost-0.9.0") is True

    # Assert a random tag name is not skipped
    assert skip_tag("sample") is False


@pytest.mark.celery(CELERY_TASK_ALWAYS_EAGER=True)
@pytest.mark.django_db
@patch("versions.tasks.import_version.run")
@patch("versions.tasks.import_release_notes.run")
@patch("versions.tasks.mark_fully_completed.run")
@patch("versions.tasks.GithubAPIClient.get_tags")
def test_import_version_race_condition(tag_mock: MagicMock, *args):
    """
    Test that when run synchronously the get_versions task does all deletion and creation
    of versions before returning
    """
    tag_mock.return_value = [{"name": "boost-1.91.0", "data": {}}]
    # This object is not competely imported, so should be deleted during import
    v, _ = Version.objects.with_partials().update_or_create(
        name="boost-1.91.0",
        defaults={
            "github_url": "",
            "beta": False,
            "full_release": True,
            "data": {},
        },
    )
    rm = ReleaseTasksManager("", "")
    # Ensure that a newly created manager has no latest version
    assert rm.latest_version is None
    rm.import_versions()
    rm_latest_version = rm.latest_version
    # Ensure that we have a latest version
    assert rm.latest_version is not None
    # Ensure that that latest version is not our previously created version
    assert rm.latest_version != v
    time.sleep(1)
    # Make sure the version doesn't change mid task run
    assert rm.latest_version == rm_latest_version
