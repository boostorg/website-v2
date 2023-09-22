from datetime import datetime
from unittest.mock import MagicMock, patch
from versions.tasks import get_release_date_for_version, skip_tag

import pytest


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

    # Assert that if the version is lower that the min, it's skipped
    assert skip_tag("boost-0.9.0") is True

    # Assert a random tag name is not skipped
    assert skip_tag("sample") is False
