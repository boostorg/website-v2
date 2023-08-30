from datetime import datetime
from unittest.mock import MagicMock, patch
from versions.tasks import get_release_date_for_version

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
