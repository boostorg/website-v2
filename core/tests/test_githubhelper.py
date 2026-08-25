import datetime
import json
from unittest.mock import MagicMock, Mock

import pytest
import requests
import responses
from ghapi.all import GhApi

from core.githubhelper import GithubAPIClient, GithubDataParser, boost_activity

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


"""boost_activity Tests"""

GRAPHQL_URL = "https://api.github.com/graphql"


def _contributions_payload(prs=None, **overrides):
    """Build a contributionsCollection GraphQL response."""
    collection = {
        "totalCommitContributions": 5,
        "totalRepositoriesWithContributedCommits": 3,
        "totalPullRequestContributions": 5,
        "totalRepositoriesWithContributedPullRequests": 5,
        "totalPullRequestReviewContributions": 2,
        "totalRepositoriesWithContributedPullRequestReviews": 1,
        "repositoryContributions": {"totalCount": 0},
        "pullRequestContributions": {"nodes": prs or []},
    }
    collection.update(overrides)
    return {"data": {"user": {"contributionsCollection": collection}}}


def _pr_node(repo, comments, title="A PR", url="https://github.com/x/y/pull/1"):
    return {
        "pullRequest": {
            "title": title,
            "url": url,
            "repository": {"nameWithOwner": repo},
            "comments": {"totalCount": comments},
        }
    }


@responses.activate
def test_boost_activity_queries_boostorg_only(settings):
    """Exactly one GraphQL call, scoped to the boostorg node ID."""
    settings.BOOST_GITHUB_ORG_NODE_ID = "O_kgDOADBg4Q"
    responses.add(responses.POST, GRAPHQL_URL, json=_contributions_payload())

    result = boost_activity("testuser")

    assert len(responses.calls) == 1
    body = json.loads(responses.calls[0].request.body)
    assert body["variables"]["orgId"] == "O_kgDOADBg4Q"
    assert body["variables"]["login"] == "testuser"
    assert result["total_commits"] == 5
    assert result["commit_repo_count"] == 3


@responses.activate
def test_boost_activity_raises_on_graphql_error():
    """A GraphQL errors payload raises instead of returning partial data."""
    responses.add(
        responses.POST,
        GRAPHQL_URL,
        json={"errors": [{"message": "Could not resolve to a node"}]},
    )

    with pytest.raises(ValueError):
        boost_activity("testuser")


@responses.activate
def test_boost_activity_raises_on_http_error():
    """A transient 502 must raise so callers keep the last good snapshot."""
    responses.add(responses.POST, GRAPHQL_URL, status=502, json={})

    with pytest.raises(requests.exceptions.HTTPError):
        boost_activity("testuser")


@responses.activate
def test_boost_activity_raises_on_unknown_login():
    """A null user is a success payload, but must not be stored as zeros."""
    responses.add(responses.POST, GRAPHQL_URL, json={"data": {"user": None}})

    with pytest.raises(ValueError):
        boost_activity("nosuchuser")


@responses.activate
def test_boost_activity_featured_pr_is_highest_comment_count():
    """The featured PR is the one with the most conversation comments."""
    responses.add(
        responses.POST,
        GRAPHQL_URL,
        json=_contributions_payload(
            prs=[
                _pr_node("boostorg/url", 5),
                _pr_node("boostorg/beast", 9),
                _pr_node("boostorg/json", 2),
            ]
        ),
    )

    featured = boost_activity("testuser")["featured_pr"]

    assert featured["repo"] == "boostorg/beast"
    assert featured["comment_count"] == 9


@responses.activate
def test_boost_activity_featured_pr_none_when_no_prs():
    responses.add(responses.POST, GRAPHQL_URL, json=_contributions_payload(prs=[]))

    assert boost_activity("testuser")["featured_pr"] is None
