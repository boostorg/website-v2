import json
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from contributions.models import ContributionType, GithubProfile, Identity
from contributions.parsers.github_issues import (
    get_issue_created,
    get_issue_contributions,
    get_library_issue_contributions,
)
from core.githubhelper import GithubAPIClient


@pytest.fixture
def mock_github_client():
    """Mock GitHub API client for testing."""
    client = MagicMock(spec=GithubAPIClient)
    return client


def load_issue_data(issue_number):
    """Load issue data for a given issue number."""
    base_path = f"contributions/tests/sample_data/website-v2_issue-{issue_number}"
    with open(f"{base_path}/issue.json") as f:
        return json.load(f)


@pytest.mark.parametrize(
    "issue_number,expected_user_id,expected_username,expected_body_text",
    [
        (1188, 1257803, "sdarwin", 'webhook "import new releases"'),
        (1897, 121198190, "rbbeeston", "AI summaries of blog posts"),
    ],
)
def test_get_issue_created_basic(
    issue_number, expected_user_id, expected_username, expected_body_text
):
    """Test that get_issue_created returns correct ParsedGithubContribution."""
    issue_data = load_issue_data(issue_number)
    github_repo = "website-v2"

    contributions = list(get_issue_created(issue_data, github_repo))

    assert len(contributions) == 1
    contribution = contributions[0]

    assert contribution.user.user_id == expected_user_id
    assert contribution.user.username == expected_username
    assert contribution.repo == "website-v2"
    assert contribution.type == ContributionType.ISSUE_CREATE
    assert contribution.info == str(issue_number)
    assert expected_body_text in contribution.comment


def test_get_issue_created_with_empty_body():
    """Test that get_issue_created handles empty issue body."""
    issue_data = load_issue_data(1188)
    issue_data["body"] = ""
    github_repo = "website-v2"

    contributions = list(get_issue_created(issue_data, github_repo))

    assert len(contributions) == 1
    contribution = contributions[0]

    # Title with empty body - no trailing newline when body is empty
    assert contribution.comment == 'webhook "import new releases"'


def test_get_issue_created_with_null_body():
    """Test that get_issue_created handles null issue body."""
    issue_data = load_issue_data(1188)
    issue_data["body"] = None
    github_repo = "website-v2"

    contributions = list(get_issue_created(issue_data, github_repo))

    assert len(contributions) == 1
    contribution = contributions[0]

    # Should handle None gracefully
    assert 'webhook "import new releases"' in contribution.comment


def test_get_issue_created_different_user():
    """Test with different user data."""
    issue_data = {
        "number": 456,
        "title": "Update documentation",
        "body": "Docs need updating",
        "author": {
            "databaseId": 99999,
            "login": "docwriter",
        },
        "createdAt": "2024-02-01T12:00:00Z",
    }
    github_repo = "boost/docs"

    contributions = list(get_issue_created(issue_data, github_repo))

    assert len(contributions) == 1
    contribution = contributions[0]

    assert contribution.user.user_id == 99999
    assert contribution.user.username == "docwriter"
    assert contribution.info == "456"


@pytest.mark.parametrize(
    "issue_number,expected_total_contributions,expected_comment_index,expected_comment_user_id,expected_comment_username,expected_close_index,expected_close_user_id,expected_reopen_index",
    [
        (1188, 16, 2, 421710, "gavinwahl", 3, 1257803, 4),
    ],
)
def test_get_issue_contributions_with_matching_events(
    issue_number,
    expected_total_contributions,
    expected_comment_index,
    expected_comment_user_id,
    expected_comment_username,
    expected_close_index,
    expected_close_user_id,
    expected_reopen_index,
):
    """Test that comments are correctly matched with timeline events."""
    issue_data = load_issue_data(issue_number)
    github_repo = "website-v2"

    contributions = list(get_issue_contributions(issue_data, github_repo))

    assert len(contributions) == expected_total_contributions

    assert contributions[expected_comment_index].type == ContributionType.ISSUE_COMMENT
    assert (
        contributions[expected_comment_index].user.user_id == expected_comment_user_id
    )
    assert (
        contributions[expected_comment_index].user.username == expected_comment_username
    )
    assert contributions[expected_comment_index].comment == "That's the exact syntax"

    assert contributions[expected_close_index].type == ContributionType.ISSUE_CLOSE
    assert contributions[expected_close_index].user.user_id == expected_close_user_id
    assert contributions[expected_close_index].user.username == "sdarwin"
    assert contributions[expected_close_index].info == str(issue_number)
    assert (
        contributions[expected_close_index].comment
        == "Thank you!   I have opened another issue in release-tools where I will add the `curl` command to `publish_release.py`.   Closing."
    )

    # Second contribution should be ISSUE_REOPENED (matched with timeline)
    assert contributions[expected_reopen_index].type == ContributionType.ISSUE_REOPENED
    assert contributions[expected_reopen_index].user.user_id == expected_close_user_id
    assert contributions[expected_reopen_index].user.username == "sdarwin"
    assert "Hi @gavinwahl" in contributions[expected_reopen_index].comment
    # There is only one closed event in timeline, because github.
    # The other one needs to be created based on the comment and
    # matched closed time ¯\_(ツ)_/¯


@pytest.mark.parametrize(
    "issue_number,expected_total_contributions",
    [
        (1188, 16),
        (1897, 4),
    ],
)
def test_get_issue_contributions_no_timeline_events(
    issue_number, expected_total_contributions
):
    """Test when there are no timeline events, only comments."""
    issue_data = load_issue_data(issue_number)
    # Remove timeline events
    issue_data["timelineItems"] = {"nodes": []}

    github_repo = "website-v2"

    contributions = list(get_issue_contributions(issue_data, github_repo))

    assert len(contributions) == expected_total_contributions
    for contribution in contributions:
        assert contribution.type in [
            ContributionType.ISSUE_COMMENT,
            ContributionType.ISSUE_CLOSE,
            ContributionType.ISSUE_REOPENED,
        ]


@pytest.mark.parametrize("issue_number", [1188])
def test_get_issue_contributions_no_comments(issue_number):
    """Test when there are timeline events but no comments."""
    issue_data = load_issue_data(issue_number)
    # Remove comments
    issue_data["comments"] = {"nodes": []}

    github_repo = "website-v2"

    contributions = list(get_issue_contributions(issue_data, github_repo))

    # Should return empty list since we iterate over comments
    assert len(contributions) == 0


def test_get_issue_contributions_ignores_unsupported_events():
    """Test that unsupported timeline events are ignored."""
    issue_data = load_issue_data(1188)

    # Replace timeline with unsupported events
    issue_data["timelineItems"] = {
        "nodes": [
            {
                "__typename": "LabeledEvent",
                "actor": {"databaseId": 12345, "login": "testuser"},
                "createdAt": "2024-01-20T15:00:00Z",
            },
            {
                "__typename": "AssignedEvent",
                "actor": {"databaseId": 12345, "login": "testuser"},
                "createdAt": "2024-01-20T15:00:00Z",
            },
        ]
    }

    github_repo = "boost/test"

    contributions = list(get_issue_contributions(issue_data, github_repo))

    # All comments should be ISSUE_COMMENT since no supported events match
    assert all(c.type == ContributionType.ISSUE_COMMENT for c in contributions)


@pytest.mark.parametrize(
    "issue_number,expected_first_datetime",
    [
        (1188, "2024-10-11T17:16:57Z"),
        (1897, "2025-08-27T00:01:23Z"),
    ],
)
def test_get_issue_contributions_datetime_parsing(
    issue_number, expected_first_datetime
):
    """Test that datetime strings are correctly parsed."""
    issue_data = load_issue_data(issue_number)
    # Remove timeline events
    issue_data["timelineItems"] = {"nodes": []}

    github_repo = "website-v2"

    contributions = list(get_issue_contributions(issue_data, github_repo))
    # Check that datetime was parsed correctly
    assert contributions[0].contributed_at == datetime.fromisoformat(
        expected_first_datetime
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "issue_number,expected_total_contributions,expected_comment_user_id,expected_comment_username",
    [
        (1188, 17, 421710, "gavinwahl"),
        (1897, 5, 2774608, "daveoconnor"),
    ],
)
def test_get_library_issue_contributions_creates_github_contributions(
    mock_github_client,
    issue_number,
    expected_total_contributions,
    expected_comment_user_id,
    expected_comment_username,
):
    """Test that get_library_issue_contributions creates GithubContribution objects."""
    issue_data = load_issue_data(issue_number)
    # Remove timeline events for this test
    issue_data["timelineItems"] = {"nodes": []}

    github_repo = "website-v2"  # a repo may have multiple libraries

    # Setup mock to return issues
    mock_github_client.get_issues_graphql.return_value = [issue_data]

    contributions = list(
        get_library_issue_contributions(github_repo, mock_github_client)
    )

    assert len(contributions) == expected_total_contributions

    # Check that GithubProfile was created for a commenter
    assert GithubProfile.objects.filter(
        github_user_id=expected_comment_user_id
    ).exists()
    profile = GithubProfile.objects.get(github_user_id=expected_comment_user_id)
    assert profile.name == expected_comment_username

    # Check contributions are GithubContribution instances
    first_contribution = contributions[0]
    assert first_contribution.type == ContributionType.ISSUE_CREATE
    assert first_contribution.repo == github_repo
    assert first_contribution.profile is not None


@pytest.mark.django_db
def test_get_library_issue_contributions_multiple_issues(mock_github_client):
    """Test processing multiple issues."""
    github_repo = "website-v2"  # a repo may have multiple libraries

    issues = [
        {
            "number": 1,
            "title": "Issue 1",
            "body": "Body 1",
            "author": {"databaseId": 111, "login": "user1"},
            "createdAt": "2024-01-01T00:00:00Z",
            "comments": {"nodes": []},
            "timelineItems": {"nodes": []},
        },
        {
            "number": 2,
            "title": "Issue 2",
            "body": "Body 2",
            "author": {"databaseId": 222, "login": "user2"},
            "createdAt": "2024-01-02T00:00:00Z",
            "comments": {"nodes": []},
            "timelineItems": {"nodes": []},
        },
    ]

    mock_github_client.get_issues_graphql.return_value = issues

    contributions = list(
        get_library_issue_contributions(github_repo, mock_github_client)
    )
    assert len(contributions) == 2
    # Check that both profiles were created
    assert GithubProfile.objects.filter(github_user_id=111).exists()
    assert GithubProfile.objects.filter(github_user_id=222).exists()


@pytest.mark.django_db
def test_get_library_issue_contributions_empty_issues(mock_github_client):
    """Test when there are no issues."""
    github_repo = "boost/empty"  # a repo may have multiple libraries

    mock_github_client.get_issues_graphql.return_value = []

    contributions = list(
        get_library_issue_contributions(github_repo, mock_github_client)
    )

    assert len(contributions) == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    "issue_number,expected_user_id,expected_username",
    [
        (1188, 1257803, "sdarwin"),
        (1897, 121198190, "rbbeeston"),
    ],
)
def test_get_library_issue_contributions_updates_existing_profile(
    mock_github_client, issue_number, expected_user_id, expected_username
):
    """Test that existing GithubProfile is updated, not duplicated."""
    issue_data = load_issue_data(issue_number)
    # Remove comments and timeline for this test
    issue_data["comments"] = {"nodes": []}
    issue_data["timelineItems"] = {"nodes": []}

    github_repo = "boost/test"  # a repo may have multiple libraries

    # Create an existing profile with different name
    existing_profile = GithubProfile.objects.create(
        github_user_id=expected_user_id, name="oldname"
    )

    mock_github_client.get_issues_graphql.return_value = [issue_data]

    list(get_library_issue_contributions(github_repo, mock_github_client))

    # Should only have one profile
    assert GithubProfile.objects.filter(github_user_id=expected_user_id).count() == 1

    # Profile should be updated with new name
    existing_profile.refresh_from_db()
    assert existing_profile.name == expected_username


@pytest.mark.django_db
@pytest.mark.parametrize(
    "issue_number,expected_total_contributions,has_close,has_reopen",
    [
        (1188, 17, True, True),
        (1897, 5, False, False),
    ],
)
def test_get_library_issue_contributions_integration(
    mock_github_client,
    issue_number,
    expected_total_contributions,
    has_close,
    has_reopen,
):
    """Test full integration of issue creation, timeline, and comments."""
    issue_data = load_issue_data(issue_number)
    github_repo = "website-v2"  # a repo may have multiple libraries

    mock_github_client.get_issues_graphql.return_value = [issue_data]

    contributions = list(
        get_library_issue_contributions(github_repo, mock_github_client)
    )

    assert len(contributions) == expected_total_contributions

    # Verify contribution types are correct
    types = [c.type for c in contributions]
    assert ContributionType.ISSUE_CREATE in types
    assert ContributionType.ISSUE_COMMENT in types

    # Only check for ISSUE_CLOSE if the issue has matching close events with comments
    if has_close:
        assert ContributionType.ISSUE_CLOSE in types

    # Only check for ISSUE_REOPENED if the issue has reopening events
    if has_reopen:
        assert ContributionType.ISSUE_REOPENED in types

    # Verify all contributions have the correct repo
    assert all(c.repo == github_repo for c in contributions)


@pytest.mark.django_db
def test_get_library_issue_contributions_creates_identity_for_new_profile(
    mock_github_client,
):
    """Test that an Identity is created when a new GithubProfile is created."""
    issue_data = {
        "number": 999,
        "title": "Test Issue",
        "body": "Test body",
        "author": {"databaseId": 999999, "login": "newgithubuser"},
        "createdAt": "2024-01-01T00:00:00Z",
        "comments": {"nodes": []},
        "timelineItems": {"nodes": []},
    }
    github_repo = "website-v2"  # a repo may have multiple libraries

    mock_github_client.get_issues_graphql.return_value = [issue_data]

    # Consume generator to trigger side effects
    list(get_library_issue_contributions(github_repo, mock_github_client))

    # Verify GithubProfile was created and has an identity
    github_profile = GithubProfile.objects.get(github_user_id=999999)
    assert github_profile.identity is not None
    assert isinstance(github_profile.identity, Identity)
    assert github_profile.identity.name == "newgithubuser"


@pytest.mark.django_db
def test_get_library_issue_contributions_does_not_create_identity_for_existing_profile(
    mock_github_client,
):
    """Test that an Identity is not created when reusing an existing GithubProfile."""
    # Create existing profile with identity
    existing_identity = Identity.objects.create(name="Existing Identity")
    existing_profile = GithubProfile.objects.create(
        github_user_id=888888, name="existinguser", identity=existing_identity
    )

    initial_identity_count = Identity.objects.count()

    issue_data = {
        "number": 888,
        "title": "Test Issue",
        "body": "Test body",
        "author": {"databaseId": 888888, "login": "existinguser"},
        "createdAt": "2024-01-01T00:00:00Z",
        "comments": {"nodes": []},
        "timelineItems": {"nodes": []},
    }
    github_repo = "website-v2"  # a repo may have multiple libraries

    mock_github_client.get_issues_graphql.return_value = [issue_data]

    # Consume generator to trigger side effects
    list(get_library_issue_contributions(github_repo, mock_github_client))

    # Should not create a new identity
    assert Identity.objects.count() == initial_identity_count
    # Should keep the existing identity
    existing_profile.refresh_from_db()
    assert existing_profile.identity == existing_identity


@pytest.mark.django_db
def test_get_library_issue_contributions_incremental_sync_no_existing_contributions(
    mock_github_client,
):
    """Test that when no contributions exist, since=None is passed (full sync)."""
    from contributions.models import GithubContribution

    github_repo = "website-v2"  # a repo may have multiple libraries

    # Ensure no contributions exist for this repo
    assert not GithubContribution.objects.filter(repo=github_repo).exists()

    issue_data = {
        "number": 1,
        "title": "Test Issue",
        "body": "Test body",
        "author": {"databaseId": 111, "login": "user1"},
        "createdAt": "2024-01-01T00:00:00Z",
        "comments": {"nodes": []},
        "timelineItems": {"nodes": []},
    }

    mock_github_client.get_issues_graphql.return_value = [issue_data]

    list(get_library_issue_contributions(github_repo, mock_github_client))

    # Verify that get_issues_graphql was called with since=None
    mock_github_client.get_issues_graphql.assert_called_once_with(
        github_repo, since=None
    )


@pytest.mark.django_db
def test_get_library_issue_contributions_incremental_sync_with_existing_contributions(
    mock_github_client,
):
    """Test that when contributions exist, since parameter uses exact timestamp."""
    from contributions.models import GithubContribution
    from datetime import timezone

    github_repo = "website-v2"  # a repo may have multiple libraries

    # Create a profile first
    profile = GithubProfile.objects.create(github_user_id=111, name="user1")

    # Create an existing contribution (timezone-aware)
    most_recent_date = datetime(2024, 1, 10, 12, 0, 0, tzinfo=timezone.utc)
    GithubContribution.objects.create(
        profile=profile,
        repo=github_repo,
        type=ContributionType.ISSUE_COMMENT,
        info="100",
        contributed_at=most_recent_date,
    )

    issue_data = {
        "number": 1,
        "title": "Test Issue",
        "body": "Test body",
        "author": {"databaseId": 111, "login": "user1"},
        "createdAt": "2024-01-15T00:00:00Z",
        "comments": {"nodes": []},
        "timelineItems": {"nodes": []},
    }

    mock_github_client.get_issues_graphql.return_value = [issue_data]

    list(get_library_issue_contributions(github_repo, mock_github_client))

    # Verify that get_issues_graphql was called with exact timestamp
    mock_github_client.get_issues_graphql.assert_called_once_with(
        github_repo, since=most_recent_date
    )


@pytest.mark.django_db
def test_get_library_issue_contributions_incremental_sync_only_queries_issue_types(
    mock_github_client,
):
    """Test that incremental sync only considers issue-related contribution types."""
    from contributions.models import GithubContribution
    from datetime import timezone

    github_repo = "website-v2"  # a repo may have multiple libraries

    # Create a profile first
    profile = GithubProfile.objects.create(github_user_id=111, name="user1")

    # Create a PR contribution (should be ignored for issue sync)
    pr_date = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    GithubContribution.objects.create(
        profile=profile,
        repo=github_repo,
        type=ContributionType.PR_CREATE,
        info="50",
        contributed_at=pr_date,
    )

    # Create an older issue contribution (should be used for since)
    issue_date = datetime(2024, 1, 10, 12, 0, 0, tzinfo=timezone.utc)
    GithubContribution.objects.create(
        profile=profile,
        repo=github_repo,
        type=ContributionType.ISSUE_CREATE,
        info="100",
        contributed_at=issue_date,
    )

    issue_data = {
        "number": 1,
        "title": "Test Issue",
        "body": "Test body",
        "author": {"databaseId": 111, "login": "user1"},
        "createdAt": "2024-01-20T00:00:00Z",
        "comments": {"nodes": []},
        "timelineItems": {"nodes": []},
    }

    mock_github_client.get_issues_graphql.return_value = [issue_data]

    list(get_library_issue_contributions(github_repo, mock_github_client))

    # Verify that since is based on issue_date (not pr_date)
    mock_github_client.get_issues_graphql.assert_called_once_with(
        github_repo, since=issue_date
    )
