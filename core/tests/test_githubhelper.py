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


def test_extract_names():
    sample = "Tester Testerson <tester -at- gmail.com>"
    expected = ["Tester", "Testerson"]
    result = GithubDataParser().extract_names(sample)
    assert expected == result

    sample = "Tester Testerson"
    expected = ["Tester", "Testerson"]
    result = GithubDataParser().extract_names(sample)
    assert expected == result

    sample = "Tester de Testerson <tester -at- gmail.com>"
    expected = ["Tester de", "Testerson"]
    result = GithubDataParser().extract_names(sample)
    assert expected == result

    sample = "Tester de Testerson"
    expected = ["Tester de", "Testerson"]
    result = GithubDataParser().extract_names(sample)
    assert expected == result

    sample = "Various"
    expected = ["Various", ""]
    result = GithubDataParser().extract_names(sample)
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
        "first_name": "Tester",
        "last_name": "Testerson",
    }
    result = GithubDataParser().extract_contributor_data(sample)
    assert expected == result

    sample = "Tester Testerson"
    expected = {
        "valid_email": False,
        "first_name": "Tester",
        "last_name": "Testerson",
    }
    result = GithubDataParser().extract_contributor_data(sample)
    assert expected["valid_email"] is False
    assert expected["first_name"] == result["first_name"]
    assert expected["last_name"] == result["last_name"]
    assert "email" in result
