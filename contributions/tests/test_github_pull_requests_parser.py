import json
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from contributions.models import ContributionType, GithubProfile
from contributions.parsers.github_pull_requests import (
    get_pr_opened,
    get_pr_timeline_contributions,
    get_pr_review_thread_contributions,
    get_library_pr_contributions,
)
from core.githubhelper import GithubAPIClient


@pytest.fixture
def mock_github_client():
    """Mock GitHub API client for testing."""
    client = MagicMock(spec=GithubAPIClient)
    return client


def load_pr_data(pr_number):
    """Load PR data for a given PR number."""
    base_path = f"contributions/tests/sample_data/website-v2_pr-{pr_number}"
    with open(f"{base_path}/pr.json") as f:
        return json.load(f)


@pytest.mark.parametrize(
    "pr_number,expected_user_id,expected_username,expected_body_text",
    [
        (1602, 2774608, "daveoconnor", "This PR isn't to be merged"),
        (2057, 2774608, "daveoconnor", "Slack data doesn't seem to have updated"),
    ],
)
def test_get_pr_opened_basic(
    pr_number, expected_user_id, expected_username, expected_body_text
):
    """Test that get_pr_opened returns correct ParsedGithubContribution."""
    pr_data = load_pr_data(pr_number)
    github_repo = "website-v2"

    contributions = list(get_pr_opened(pr_data, github_repo))

    assert len(contributions) == 1
    contribution = contributions[0]

    assert contribution.user.user_id == expected_user_id
    assert contribution.user.username == expected_username
    assert contribution.repo == "website-v2"
    assert contribution.type == ContributionType.PR_CREATE
    assert contribution.info == str(pr_number)
    assert expected_body_text in contribution.comment


def test_get_pr_opened_with_empty_body():
    """Test that get_pr_opened handles empty PR body."""
    pr_data = load_pr_data(1602)
    pr_data["body"] = ""
    github_repo = "website-v2"

    contributions = list(get_pr_opened(pr_data, github_repo))

    assert len(contributions) == 1
    contribution = contributions[0]
    # Title and empty body
    assert contribution.comment == "Added nix for developer setup (#1379)"


def test_get_pr_opened_with_null_body():
    """Test that get_pr_opened handles null PR body."""
    pr_data = load_pr_data(1602)
    pr_data["body"] = None
    github_repo = "website-v2"

    contributions = list(get_pr_opened(pr_data, github_repo))

    assert len(contributions) == 1
    contribution = contributions[0]
    # Should handle None gracefully
    assert "Added nix for developer setup (#1379)" in contribution.comment


def test_get_pr_opened_different_user():
    """Test with different user data."""
    pr_data = {
        "number": 789,
        "title": "Update documentation",
        "body": "Update documentation for new feature",
        "author": {
            "databaseId": 99999,
            "login": "docwriter",
        },
        "createdAt": "2025-02-01T12:00:00Z",
    }
    github_repo = "boost/docs"

    contributions = list(get_pr_opened(pr_data, github_repo))

    assert len(contributions) == 1
    contribution = contributions[0]

    assert contribution.user.user_id == 99999
    assert contribution.user.username == "docwriter"
    assert contribution.info == "789"
    assert contribution.repo == "boost/docs"


@pytest.mark.parametrize(
    "pr_number,expected_comment_count",
    [
        (1602, 7),  # Number of IssueComment events in timeline
        (2057, 0),  # No comments in timeline, only merge/close events
    ],
)
def test_get_pr_timeline_contributions_with_comments(pr_number, expected_comment_count):
    """Test extracting comments from timeline."""
    pr_data = load_pr_data(pr_number)
    github_repo = "website-v2"

    contributions = list(get_pr_timeline_contributions(pr_data, github_repo))

    # Filter for just comments
    comment_contributions = [
        c for c in contributions if c.type == ContributionType.PR_COMMENT
    ]
    assert len(comment_contributions) == expected_comment_count

    for contribution in contributions:
        assert contribution.type in [
            ContributionType.PR_COMMENT,
            ContributionType.PR_CLOSE,
            ContributionType.PR_MERGE,
        ]
        assert contribution.repo == github_repo
        assert contribution.info == str(pr_number)


@pytest.mark.parametrize(
    "pr_number,has_merge",
    [
        (1602, True),  # This PR was merged
        (2057, True),  # This PR was also merged
    ],
)
def test_get_pr_timeline_contributions_with_merge(pr_number, has_merge):
    """Test extracting merged events from timeline."""
    pr_data = load_pr_data(pr_number)
    github_repo = "website-v2"

    contributions = list(get_pr_timeline_contributions(pr_data, github_repo))

    types = [c.type for c in contributions]

    if has_merge:
        assert ContributionType.PR_MERGE in types
    else:
        assert ContributionType.PR_MERGE not in types


def test_get_pr_timeline_contributions_filters_unsupported_events():
    """Test that unsupported timeline events are ignored."""
    pr_data = load_pr_data(1602)

    # Replace timeline with unsupported events
    pr_data["timelineItems"] = {
        "nodes": [
            {
                "__typename": "ReviewRequestedEvent",
                "actor": {"databaseId": 12345, "login": "testuser"},
                "createdAt": "2025-01-20T15:00:00Z",
            },
            {
                "__typename": "HeadRefForcePushedEvent",
                "actor": {"databaseId": 12345, "login": "testuser"},
                "createdAt": "2025-01-20T16:00:00Z",
            },
            {
                "__typename": "IssueComment",
                "id": "IC_test",
                "body": "This is a comment",
                "author": {"databaseId": 12345, "login": "testuser"},
                "createdAt": "2025-01-20T17:00:00Z",
            },
        ]
    }

    github_repo = "website-v2"

    contributions = list(get_pr_timeline_contributions(pr_data, github_repo))

    # Only the IssueComment event should be included
    assert len(contributions) == 1
    assert contributions[0].type == ContributionType.PR_COMMENT


def test_get_pr_timeline_contributions_with_merged_and_closed():
    """Test timeline with merged and closed events."""
    pr_data = {
        "number": 999,
        "timelineItems": {
            "nodes": [
                {
                    "__typename": "MergedEvent",
                    "id": "ME_test1",
                    "actor": {"databaseId": 1111, "login": "merger"},
                    "createdAt": "2025-01-30T10:00:00Z",
                },
                {
                    "__typename": "ClosedEvent",
                    "id": "CE_test2",
                    "actor": {"databaseId": 2222, "login": "closer"},
                    "createdAt": "2025-01-30T10:01:00Z",
                },
            ]
        },
    }

    contributions = list(get_pr_timeline_contributions(pr_data, "test-repo"))

    assert len(contributions) == 2

    # Check merged event
    assert contributions[0].type == ContributionType.PR_MERGE
    assert contributions[0].user.user_id == 1111
    assert contributions[0].user.username == "merger"

    # Check closed event
    assert contributions[1].type == ContributionType.PR_CLOSE
    assert contributions[1].user.user_id == 2222
    assert contributions[1].user.username == "closer"


@pytest.mark.parametrize(
    "pr_number,expected_review_count",
    [
        (1602, 0),  # No review thread comments
        (2057, 2),  # Two review thread comments
    ],
)
def test_get_pr_review_thread_contributions(pr_number, expected_review_count):
    """Test extracting review thread comments."""
    pr_data = load_pr_data(pr_number)
    github_repo = "website-v2"

    contributions = list(get_pr_review_thread_contributions(pr_data, github_repo))

    assert len(contributions) == expected_review_count

    for contribution in contributions:
        assert contribution.type == ContributionType.PR_REVIEW
        assert contribution.repo == github_repo
        assert contribution.info == str(pr_number)


def test_get_pr_review_thread_contributions_empty_threads():
    """Test when there are no review threads."""
    pr_data = {"number": 999, "reviewThreads": {"nodes": []}}

    contributions = list(get_pr_review_thread_contributions(pr_data, "test-repo"))

    assert len(contributions) == 0


def test_get_pr_review_thread_contributions_filters_ghost_users():
    """Test that review comments from deleted users are filtered."""
    pr_data = {
        "number": 999,
        "reviewThreads": {
            "nodes": [
                {
                    "comments": {
                        "nodes": [
                            {
                                "__typename": "PullRequestReviewComment",
                                "id": "PRRC_test",
                                "body": "Ghost comment",
                                "createdAt": "2025-01-20T10:00:00Z",
                                "author": None,  # Ghost user
                            }
                        ]
                    }
                }
            ]
        },
    }

    contributions = list(get_pr_review_thread_contributions(pr_data, "test-repo"))

    # Ghost user comments should be filtered out
    assert len(contributions) == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    "pr_number,expected_user_id,expected_username",
    [
        (1602, 2774608, "daveoconnor"),
        (2057, 2774608, "daveoconnor"),
    ],
)
def test_get_library_pr_contributions_creates_github_contributions(
    mock_github_client, pr_number, expected_user_id, expected_username
):
    """Test that get_library_pr_contributions creates GithubContribution objects."""
    pr_data = load_pr_data(pr_number)
    github_repo = "website-v2"

    # Setup mock to return GraphQL format
    mock_github_client.get_prs_graphql.return_value = [pr_data]

    contributions = list(get_library_pr_contributions(github_repo, mock_github_client))

    # Should have at least PR_CREATE
    assert len(contributions) >= 1

    # Check that GithubProfile was created
    assert GithubProfile.objects.filter(github_user_id=expected_user_id).exists()
    profile = GithubProfile.objects.get(github_user_id=expected_user_id)
    assert profile.name == expected_username

    # Check contributions are GithubContribution instances
    first_contribution = contributions[0]
    assert first_contribution.type == ContributionType.PR_CREATE
    assert first_contribution.repo == github_repo
    assert first_contribution.profile is not None


@pytest.mark.django_db
def test_get_library_pr_contributions_multiple_prs(mock_github_client):
    """Test processing multiple pull requests."""
    github_repo = "website-v2"

    prs = [
        {
            "number": 1,
            "title": "First PR",
            "body": "First PR body",
            "author": {"databaseId": 111, "login": "user1"},
            "createdAt": "2025-01-01T00:00:00Z",
            "timelineItems": {"nodes": []},
            "reviewThreads": {"nodes": []},
        },
        {
            "number": 2,
            "title": "Second PR",
            "body": "Second PR body",
            "author": {"databaseId": 222, "login": "user2"},
            "createdAt": "2025-01-02T00:00:00Z",
            "timelineItems": {"nodes": []},
            "reviewThreads": {"nodes": []},
        },
    ]

    mock_github_client.get_prs_graphql.return_value = prs

    contributions = list(get_library_pr_contributions(github_repo, mock_github_client))

    # Should have 2 PR_CREATE contributions
    assert len(contributions) == 2

    # Check that both profiles were created
    assert GithubProfile.objects.filter(github_user_id=111).exists()
    assert GithubProfile.objects.filter(github_user_id=222).exists()


@pytest.mark.django_db
def test_get_library_pr_contributions_empty_prs(mock_github_client):
    """Test when there are no pull requests."""
    github_repo = "boost/empty"

    mock_github_client.get_prs_graphql.return_value = []

    contributions = list(get_library_pr_contributions(github_repo, mock_github_client))

    assert len(contributions) == 0


@pytest.mark.django_db
@pytest.mark.parametrize("pr_number", [1602, 2057])
def test_get_library_pr_contributions_updates_existing_profile(
    mock_github_client, pr_number
):
    """Test that existing GithubProfile is updated, not duplicated."""
    pr_data = load_pr_data(pr_number)
    github_repo = "website-v2"

    # Create an existing profile with different name
    existing_profile = GithubProfile.objects.create(
        github_user_id=2774608, name="oldname"
    )

    mock_github_client.get_prs_graphql.return_value = [pr_data]

    list(get_library_pr_contributions(github_repo, mock_github_client))

    # Should only have one profile
    assert GithubProfile.objects.filter(github_user_id=2774608).count() == 1

    # Profile should be updated with new name
    existing_profile.refresh_from_db()
    assert existing_profile.name == "daveoconnor"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "pr_number,expected_min_contributions",
    [
        (1602, 10),  # PR_CREATE + 7 comments + merge + close
        (2057, 5),  # PR_CREATE + 2 review threads + merge + close
    ],
)
def test_get_library_pr_contributions_integration(
    mock_github_client, pr_number, expected_min_contributions
):
    """Test full integration of PR creation, timeline, and reviews."""
    pr_data = load_pr_data(pr_number)
    github_repo = "website-v2"

    mock_github_client.get_prs_graphql.return_value = [pr_data]

    contributions = list(get_library_pr_contributions(github_repo, mock_github_client))

    # Should have at least the expected number of contributions
    assert len(contributions) >= expected_min_contributions

    # Verify contribution types are present
    types = [c.type for c in contributions]
    assert ContributionType.PR_CREATE in types

    # Verify all contributions have the correct repo
    assert all(c.repo == github_repo for c in contributions)


@pytest.mark.django_db
def test_get_library_pr_contributions_incremental_sync_no_existing_contributions(
    mock_github_client,
):
    """Test that when no contributions exist, since=None is passed (full sync)."""
    from contributions.models import GithubContribution

    github_repo = "website-v2"

    # Ensure no contributions exist for this repo
    assert not GithubContribution.objects.filter(repo=github_repo).exists()

    pr_data = {
        "number": 1,
        "title": "Test PR",
        "body": "Test body",
        "author": {"databaseId": 111, "login": "user1"},
        "createdAt": "2024-01-01T00:00:00Z",
        "timelineItems": {"nodes": []},
        "reviews": {"nodes": []},
        "reviewThreads": {"nodes": []},
    }

    mock_github_client.get_prs_graphql.return_value = [pr_data]

    list(get_library_pr_contributions(github_repo, mock_github_client))

    # Verify that get_prs_graphql was called with since=None
    mock_github_client.get_prs_graphql.assert_called_once_with(github_repo, since=None)


@pytest.mark.django_db
def test_get_library_pr_contributions_incremental_sync_with_existing_contributions(
    mock_github_client,
):
    """Test that when contributions exist, since parameter uses exact timestamp."""
    from contributions.models import GithubContribution, GithubProfile
    from datetime import timezone

    github_repo = "website-v2"

    # Create a profile first
    profile = GithubProfile.objects.create(github_user_id=111, name="user1")

    # Create an existing contribution (timezone-aware)
    most_recent_date = datetime(2024, 1, 10, 12, 0, 0, tzinfo=timezone.utc)
    GithubContribution.objects.create(
        profile=profile,
        repo=github_repo,
        type=ContributionType.PR_COMMENT,
        info="100",
        contributed_at=most_recent_date,
    )

    pr_data = {
        "number": 1,
        "title": "Test PR",
        "body": "Test body",
        "author": {"databaseId": 111, "login": "user1"},
        "createdAt": "2024-01-15T00:00:00Z",
        "timelineItems": {"nodes": []},
        "reviews": {"nodes": []},
        "reviewThreads": {"nodes": []},
    }

    mock_github_client.get_prs_graphql.return_value = [pr_data]

    list(get_library_pr_contributions(github_repo, mock_github_client))

    # Verify that get_prs_graphql was called with exact timestamp
    mock_github_client.get_prs_graphql.assert_called_once_with(
        github_repo, since=most_recent_date
    )


@pytest.mark.django_db
def test_get_library_pr_contributions_incremental_sync_only_queries_pr_types(
    mock_github_client,
):
    """Test that incremental sync only considers PR-related contribution types."""
    from contributions.models import GithubContribution, GithubProfile
    from datetime import timezone

    github_repo = "website-v2"

    # Create a profile first
    profile = GithubProfile.objects.create(github_user_id=111, name="user1")

    # Create an issue contribution (should be ignored for PR sync)
    issue_date = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    GithubContribution.objects.create(
        profile=profile,
        repo=github_repo,
        type=ContributionType.ISSUE_CREATE,
        info="50",
        contributed_at=issue_date,
    )

    # Create an older PR contribution (should be used for since)
    pr_date = datetime(2024, 1, 10, 12, 0, 0, tzinfo=timezone.utc)
    GithubContribution.objects.create(
        profile=profile,
        repo=github_repo,
        type=ContributionType.PR_CREATE,
        info="100",
        contributed_at=pr_date,
    )

    pr_data = {
        "number": 1,
        "title": "Test PR",
        "body": "Test body",
        "author": {"databaseId": 111, "login": "user1"},
        "createdAt": "2024-01-20T00:00:00Z",
        "timelineItems": {"nodes": []},
        "reviews": {"nodes": []},
        "reviewThreads": {"nodes": []},
    }

    mock_github_client.get_prs_graphql.return_value = [pr_data]

    list(get_library_pr_contributions(github_repo, mock_github_client))

    # Verify that since is based on pr_date (not issue_date)
    mock_github_client.get_prs_graphql.assert_called_once_with(
        github_repo, since=pr_date
    )
