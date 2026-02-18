import datetime
from unittest.mock import MagicMock, Mock

import pytest
import responses
from ghapi.all import GhApi

from core.githubhelper import GithubAPIClient, GithubDataParser

"""GithubAPIClient Tests"""


@pytest.fixture
def github_api_client():
    return GithubAPIClient()


@pytest.fixture
def github_api_client_mock():
    """ """
    mock = MagicMock()
    return mock


def test_initialize_api():
    """Test the initialize_api method of GitHubAPIClient."""
    api = GithubAPIClient().initialize_api()
    assert isinstance(api, GhApi)


def test_get_blob(github_api_client):
    """Test the get_blob method of GitHubAPIClient."""
    github_api_client.api.git.get_blob = MagicMock(
        return_value={"sha": "12345", "content": "example content", "encoding": "utf-8"}
    )
    result = github_api_client.get_blob(repo_slug="sample_repo", file_sha="12345")
    assert result == {"sha": "12345", "content": "example content", "encoding": "utf-8"}
    github_api_client.api.git.get_blob.assert_called_with(
        owner=github_api_client.owner, repo="sample_repo", file_sha="12345"
    )


@responses.activate
def test_get_libraries_json(github_api_client):
    """Test the get_libraries_json method of GitHubAPIClient."""
    repo_slug = "sample_repo"
    url = f"https://raw.githubusercontent.com/{github_api_client.owner}/{repo_slug}/master/meta/libraries.json"
    sample_json = {"key": "math", "name": "Math"}
    responses.add(
        responses.GET,
        url,
        json=sample_json,
        status=200,
        content_type="application/json",
    )
    result = github_api_client.get_libraries_json(repo_slug=repo_slug)
    assert result == {"key": "math", "name": "Math"}
    assert len(responses.calls) == 1
    assert responses.calls[0].request.url == url


def test_get_ref(github_api_client):
    """Test the get_ref method of GitHubAPIClient."""
    github_api_client.api.git.get_ref = MagicMock(
        return_value={"content": "example content"}
    )
    result = github_api_client.get_ref(repo_slug="sample_repo", ref="head/main")
    assert result == {"content": "example content"}


def test_get_repo(github_api_client):
    """Test the get_repo method of GitHubAPIClient."""
    github_api_client.api.repos.get = MagicMock(
        return_value={"content": "example content"}
    )
    result = github_api_client.get_repo(repo_slug="sample_repo")
    assert result == {"content": "example content"}


"""Parser Tests"""


def create_mock_commit(date):
    """Create a mock commit with the given date."""
    commit = Mock()
    commit.commit.author.date = date
    return commit


def test_get_commits_per_month():
    # Construct the mock commits.
    commits = [
        create_mock_commit(datetime.datetime(2023, 1, 15).isoformat()),
        create_mock_commit(datetime.datetime(2022, 1, 10).isoformat()),
        create_mock_commit(datetime.datetime(2022, 2, 1).isoformat()),
        create_mock_commit(datetime.datetime(2023, 1, 16).isoformat()),
    ]

    # Construct the object and call the method.
    parser = GithubDataParser()
    results = parser.get_commits_per_month(commits)

    # Check the result.
    expected = {
        datetime.datetime(2022, 1, 1).date(): 1,
        datetime.datetime(2022, 2, 1).date(): 1,
        datetime.datetime(2023, 1, 1).date(): 2,
    }
    assert expected == results


def test_parse_gitmodules():
    sample_gitmodules = """
[submodule "system"]
    path = libs/system
    url = ../system.git
    fetchRecurseSubmodules = on-demand
    branch = .
[submodule "multi_array"]
    path = libs/multi_array
    url = ../multi_array.git
    fetchRecurseSubmodules = on-demand
    branch = .
"""

    parser = GithubDataParser()
    parsed_data = parser.parse_gitmodules(sample_gitmodules)

    expected_output = [
        {
            "module": "system",
            "url": "system",
        },
        {
            "module": "multi_array",
            "url": "multi_array",
        },
    ]

    assert parsed_data == expected_output


def test_parse_libraries_json():
    sample_libraries_json = {
        "key": "math",
        "name": "Math",
        "authors": [],
        "description": "Sample Description",
        "category": ["Math"],
        "maintainers": [],
        "cxxstd": "14",
        "modules": True,
    }

    parser = GithubDataParser()
    parser.parse_libraries_json(sample_libraries_json)


def test_parse_commit():
    commit_data = {
        "committer": {"date": "2023-05-10T00:00:00Z"},
        "message": "This is a sample description for a commit",
        "html_url": "http://example.com/commit/12345",
    }
    expected = {
        "release_date": datetime.date(2023, 5, 10),
        "description": commit_data["message"],
        "github_url": "http://example.com/commit/12345",
        "data": commit_data,
    }
    result = GithubDataParser().parse_commit(commit_data)
    assert result == expected


def test_parse_tag():
    tag_data = {
        "published_at": "2023-05-10T00:00:00Z",
        "body": "This is a sample description for a tag",
        "html_url": "http://example.com/commit/12345",
    }
    expected = {
        "release_date": datetime.date(2023, 5, 10),
        "description": "This is a sample description for a tag",
        "github_url": "http://example.com/commit/12345",
        "data": tag_data,
    }
    result = GithubDataParser().parse_tag(tag_data)
    assert result == expected


@pytest.mark.parametrize(
    "sample, expected",
    [
        ("Tester Testerson <tester -at- gmail.com>", "Tester Testerson"),
        ("Tester Testerson", "Tester Testerson"),
        ("Tester de Testerson <tester -at- gmail.com>", "Tester de Testerson"),
        ("Tester de Testerson", "Tester de Testerson"),
        ("Various", "Various"),
    ],
)
def test_extract_name(sample, expected):
    result = GithubDataParser().extract_name(sample)
    assert expected == result


def test_extract_email():
    expected = "t_testerson@example.com"
    result = GithubDataParser().extract_email(
        "Tester Testerston <t_testerson -at- example.com>"
    )
    assert expected == result

    expected = "t.t.testerson@example.com"
    result = GithubDataParser().extract_email(
        "Tester Testerston <t.t.testerson -at- example.com>"
    )
    assert expected == result

    expected = "t.t.testerson@example.sample.com"
    result = GithubDataParser().extract_email(
        "Tester Testerston <t.t.testerson -at- example.sample.com> "
    )
    assert expected == result

    expected = None
    result = GithubDataParser().extract_email("Tester Testeron")
    assert expected == result

    expected = "t_tester@example.com"
    result = GithubDataParser().extract_email(
        "Tester Testerston <t -underscore- tester -at- example -dot- com> "
    )
    assert expected == result

    expected = "tester@example.com"
    result = GithubDataParser().extract_email(
        "Tester Testerston <tester - at - example.com> "
    )
    assert expected == result


def test_extract_contributor_data():
    sample = "Tester Testerson <tester -at- gmail.com>"
    expected = {
        "valid_email": True,
        "email": "tester@gmail.com",
        "display_name": "Tester Testerson",
    }
    result = GithubDataParser().extract_contributor_data(sample)
    assert expected == result

    sample = "Tester Testerson"
    expected = {
        "valid_email": False,
        "display_name": "Tester Testerson",
    }
    result = GithubDataParser().extract_contributor_data(sample)
    assert expected["valid_email"] is False
    assert expected["display_name"] == result["display_name"]
    assert "email" in result


"""GraphQL API Tests"""


def test_get_prs_graphql_without_since(github_api_client):
    """Test that get_prs_graphql returns all PRs when since is not provided."""
    # Mock the execute_graphql method to return sample PR data
    pr_data = [
        {"number": 1, "title": "PR 1", "updatedAt": "2024-01-01T00:00:00Z"},
        {"number": 2, "title": "PR 2", "updatedAt": "2024-01-15T00:00:00Z"},
    ]

    github_api_client.execute_graphql = MagicMock(
        return_value={
            "data": {
                "repository": {
                    "pullRequests": {
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "nodes": pr_data,
                    }
                }
            }
        }
    )

    result = list(github_api_client.get_prs_graphql("test_repo"))

    assert len(result) == 2
    assert result[0]["number"] == 1
    assert result[1]["number"] == 2


def test_get_prs_graphql_with_since_filters_old_prs(github_api_client):
    """Test that get_prs_graphql filters out PRs updated before the since date (client-side)."""
    # Mock the execute_graphql method to return PRs with various update dates
    pr_data = [
        {"number": 1, "title": "Old PR", "updatedAt": "2024-01-01T00:00:00Z"},
        {"number": 2, "title": "Recent PR", "updatedAt": "2024-01-15T00:00:00Z"},
        {"number": 3, "title": "Very Recent PR", "updatedAt": "2024-01-20T00:00:00Z"},
    ]

    github_api_client.execute_graphql = MagicMock(
        return_value={
            "data": {
                "repository": {
                    "pullRequests": {
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "nodes": pr_data,
                    }
                }
            }
        }
    )

    # Filter to only PRs updated after 2024-01-10
    since_date = datetime.datetime(2024, 1, 10, tzinfo=datetime.timezone.utc)
    result = list(github_api_client.get_prs_graphql("test_repo", since=since_date))

    # Should only return PRs 2 and 3
    assert len(result) == 2
    assert result[0]["number"] == 2
    assert result[1]["number"] == 3


def test_get_prs_graphql_with_since_at_boundary(github_api_client):
    """Test that get_prs_graphql correctly handles PRs at the since boundary."""
    pr_data = [
        {"number": 1, "title": "Before", "updatedAt": "2024-01-10T11:59:59Z"},
        {"number": 2, "title": "Exactly at", "updatedAt": "2024-01-10T12:00:00Z"},
        {"number": 3, "title": "After", "updatedAt": "2024-01-10T12:00:01Z"},
    ]

    github_api_client.execute_graphql = MagicMock(
        return_value={
            "data": {
                "repository": {
                    "pullRequests": {
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "nodes": pr_data,
                    }
                }
            }
        }
    )

    since_date = datetime.datetime(2024, 1, 10, 12, 0, 0, tzinfo=datetime.timezone.utc)
    result = list(github_api_client.get_prs_graphql("test_repo", since=since_date))

    # Should return PRs at or after the exact time
    assert len(result) == 2
    assert result[0]["number"] == 2
    assert result[1]["number"] == 3


def test_get_issues_graphql_without_since(github_api_client):
    """Test that get_issues_graphql uses unfiltered query when since is not provided."""
    issue_data = [
        {"number": 1, "title": "Issue 1", "updatedAt": "2024-01-01T00:00:00Z"},
        {"number": 2, "title": "Issue 2", "updatedAt": "2024-01-15T00:00:00Z"},
    ]

    github_api_client.execute_graphql = MagicMock(
        return_value={
            "data": {
                "repository": {
                    "issues": {
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "nodes": issue_data,
                    }
                }
            }
        }
    )

    result = list(github_api_client.get_issues_graphql("test_repo"))

    assert len(result) == 2
    # Verify the query used didn't include a since parameter
    call_args = github_api_client.execute_graphql.call_args
    assert "since" not in call_args[0][1]  # Check variables dict


def test_get_issues_graphql_with_since_uses_filtered_query(github_api_client):
    """Test that get_issues_graphql uses filtered query when since is provided (server-side)."""
    issue_data = [
        {"number": 2, "title": "Recent Issue", "updatedAt": "2024-01-15T00:00:00Z"},
    ]

    github_api_client.execute_graphql = MagicMock(
        return_value={
            "data": {
                "repository": {
                    "issues": {
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "nodes": issue_data,
                    }
                }
            }
        }
    )

    since_date = datetime.datetime(2024, 1, 10, tzinfo=datetime.timezone.utc)
    result = list(github_api_client.get_issues_graphql("test_repo", since=since_date))

    assert len(result) == 1
    # Verify the query used included a since parameter
    call_args = github_api_client.execute_graphql.call_args
    assert "since" in call_args[0][1]  # Check variables dict
    # Accept both Z and +00:00 formats for UTC
    since_value = call_args[0][1]["since"]
    assert since_value in ("2024-01-10T00:00:00Z", "2024-01-10T00:00:00+00:00")


"""ETag Tests"""


@pytest.mark.django_db
@responses.activate
def test_get_commits_etag_no_changes(github_api_client):
    """Test that get_commits returns empty when ETag indicates no changes (304)."""
    from contributions.models import GitRepoETag

    # Setup: store an ETag
    GitRepoETag.objects.create(repo="test_repo", etag='"abc123"')

    # Mock 304 response for ETag check
    responses.add(
        responses.GET,
        "https://api.github.com/repos/boostorg/test_repo/commits",
        status=304,
    )

    since_date = datetime.datetime(2024, 1, 10, tzinfo=datetime.timezone.utc)
    result = list(github_api_client.get_commits("test_repo", since=since_date))

    assert len(result) == 0
    assert len(responses.calls) == 1
    # Verify If-None-Match header was sent
    assert responses.calls[0].request.headers["If-None-Match"] == '"abc123"'


@pytest.mark.django_db
@responses.activate
def test_get_commits_etag_has_changes(github_api_client):
    """Test that get_commits fetches commits when ETag indicates changes (200)."""
    from contributions.models import GitRepoETag

    # Setup: store an ETag
    stored_etag = GitRepoETag.objects.create(repo="test_repo", etag='"abc123"')

    # Mock 200 response for ETag check with new ETag
    responses.add(
        responses.GET,
        "https://api.github.com/repos/boostorg/test_repo/commits",
        json=[{"sha": "commit1"}],
        status=200,
        headers={"ETag": '"def456"'},
    )

    # Create commit object matching paged API structure
    commit_obj = {
        "sha": "commit1",
        "commit": {
            "author": {
                "name": "Test Author",
                "email": "test@example.com",
                "date": "2024-01-15T00:00:00Z",
            },
            "message": "Test commit",
        },
        "parents": [],
    }

    # Mock the paged commits fetch - paged returns pages (lists) of commits
    github_api_client.api.repos.list_commits = MagicMock(
        return_value=iter([[commit_obj]])
    )

    since_date = datetime.datetime(2024, 1, 10, tzinfo=datetime.timezone.utc)
    result = list(github_api_client.get_commits("test_repo", since=since_date))

    # Verify commits were returned (paged returns pages of commits)
    assert len(result) > 0

    # Verify ETag was updated (from check request, no separate update request)
    stored_etag.refresh_from_db()
    assert stored_etag.etag == '"def456"'


@pytest.mark.django_db
@responses.activate
def test_get_commits_no_etag_stored(github_api_client):
    """Test that get_commits works with fake ETag when no ETag is stored yet (first sync)."""
    commit_obj = {
        "sha": "commit1",
        "commit": {
            "author": {
                "name": "Test Author",
                "email": "test@example.com",
                "date": "2024-01-15T00:00:00Z",
            },
            "message": "Test commit",
        },
        "parents": [],
    }

    # Mock the ETag check request (will use fake ETag since none stored)
    responses.add(
        responses.GET,
        "https://api.github.com/repos/boostorg/test_repo/commits",
        json=[{"sha": "commit1"}],
        status=200,
        headers={"ETag": '"xyz789"'},
    )

    # Mock the paged commits fetch
    github_api_client.api.repos.list_commits = MagicMock(
        return_value=iter([[commit_obj]])
    )

    since_date = datetime.datetime(2024, 1, 10, tzinfo=datetime.timezone.utc)
    result = list(github_api_client.get_commits("test_repo", since=since_date))

    # Verify commits were returned
    assert len(result) > 0

    # Verify fake ETag was sent in check request
    assert responses.calls[0].request.headers["If-None-Match"] == '"initial-sync"'

    # Verify ETag was stored (from check request)
    from contributions.models import GitRepoETag

    assert GitRepoETag.objects.filter(repo="test_repo").exists()
    etag_record = GitRepoETag.objects.get(repo="test_repo")
    assert etag_record.etag == '"xyz789"'


@pytest.mark.django_db
@responses.activate
def test_get_commits_first_full_sync(github_api_client):
    """Test that get_commits performs ETag check with fake ETag on first full sync (no since param)."""
    commit_obj = {
        "sha": "commit1",
        "commit": {
            "author": {
                "name": "Test Author",
                "email": "test@example.com",
                "date": "2024-01-15T00:00:00Z",
            },
            "message": "Test commit",
        },
        "parents": [],
    }

    # Mock the ETag check request (will use fake ETag since none stored)
    responses.add(
        responses.GET,
        "https://api.github.com/repos/boostorg/test_repo/commits",
        json=[{"sha": "commit1"}],
        status=200,
        headers={"ETag": '"initial123"'},
    )

    # Mock the paged commits fetch
    github_api_client.api.repos.list_commits = MagicMock(
        return_value=iter([[commit_obj]])
    )

    result = list(github_api_client.get_commits("test_repo"))

    # Verify commits were returned
    assert len(result) > 0

    # Verify fake ETag was sent in check request
    assert responses.calls[0].request.headers["If-None-Match"] == '"initial-sync"'

    # Verify ETag was stored (from check request)
    from contributions.models import GitRepoETag

    assert GitRepoETag.objects.filter(repo="test_repo").exists()
    etag_record = GitRepoETag.objects.get(repo="test_repo")
    assert etag_record.etag == '"initial123"'
