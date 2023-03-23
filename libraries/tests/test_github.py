from unittest.mock import Mock, patch

import pytest
import responses
from dateutil.parser import parse
from ghapi.all import GhApi
from model_bakery import baker

from libraries.github import (
    GithubAPIClient,
    GithubUpdater,
    LibraryUpdater,
    get_api,
    get_user_by_username,
)
from libraries.models import Issue, Library, PullRequest


@pytest.fixture(scope="function")
def mock_api() -> GhApi:
    """Fixture that mocks the GitHub API."""
    with patch("libraries.github_new.GhApi") as mock_api_class:
        yield mock_api_class.return_value


def test_initialize_api():
    """Test the initialize_api method of GitHubAPIClient."""
    api = GithubAPIClient().initialize_api()
    assert isinstance(api, GhApi)


@pytest.mark.xfail(
    reason="fastcore.basics.HTTP422UnprocessableEntityError: HTTP Error 422: Unprocessable Entity"
)
def test_get_blob(mock_api):
    """Test the get_blob method of GitHubAPIClient."""
    # Set up mock objects
    mock_api.api.git.get_blob.return_value = {"content": "example content"}
    file_sha = "abc123"
    result = GithubAPIClient().get_blob(file_sha=file_sha)
    # get_blob_mock.assert_called_once_with(owner=owner, repo=repo_slug, file_sha=file_sha)
    assert result == {"content": "example content"}


@pytest.mark.xfail(
    reason="AssertionError: assert None == {'libraries': [{'description': 'example description', 'name': 'example'}]}"
)
def test_get_libraries_json_file():
    """Test the get_libraries_json_file method of GitHubAPIClient."""
    import json
    from requests.models import Response

    json_data = {
        "libraries": [{"name": "example", "description": "example description"}]
    }

    # Convert the dictionary to a JSON string
    json_string = json.dumps(json_data)
    response_mock = Response()
    response_mock.status_code = 200
    response_mock._content = json_string.encode("utf-8")
    # Set up mock objects
    api_mock = Mock()
    get_mock = Mock()
    get_mock.return_value = response_mock
    api_mock.get = get_mock

    owner = "my_username"
    repo_slug = "my_repo"
    result = GithubAPIClient().get_libraries_json_file(repo_slug)
    assert result == {
        "libraries": [{"name": "example", "description": "example description"}]
    }


def test_get_ref(requests_mock):
    """Test the get_ref method of GitHubAPIClient."""
    client = GithubAPIClient()
    client.owner = "my_username"
    client.repo_slug = "my_repo"
    client.ref = "refs/heads/main"
    expected_output = {
        "ref": "refs/heads/main",
        "node_id": "MDM6UmVmMzI4MDg4MzI0OnJlZnMvaGVhZHMvbWFpbg==",
        "url": "https://api.github.com/repos/my_username/my_repo/git/refs/heads/main",
        "object": {
            "sha": "5d5dcb6b02705b2f56f7d5f10874c72632b91952",
            "type": "commit",
            "url": "https://api.github.com/repos/my_username/my_repo/git/commits/5d5dcb6b02705b2f56f7d5f10874c72632b91952",
        },
    }
    requests_mock.get(
        f"https://api.github.com/repos/{my_class.owner}/{my_class.repo_slug}/git/refs/{my_class.ref}",
        json=expected_output,
    )
    result = client.get_ref()
    assert result == expected_output

    # Test with explicit parameters
    owner = "my_username"
    repo_slug = "my_repo"
    ref = "refs/heads/develop"
    expected_output = {
        "ref": "refs/heads/develop",
        "node_id": "MDM6UmVmMzI4MDg4MzI0OnJlZnMvaGVhZHMvbWFpbg==",
        "url": "https://api.github.com/repos/my_username/my_repo/git/refs/heads/develop",
        "object": {
            "sha": "5d5dcb6b02705b2f56f7d5f10874c72632b91952",
            "type": "commit",
            "url": "https://api.github.com/repos/my_username/my_repo/git/commits/5d5dcb6b02705b2f56f7d5f10874c72632b91952",
        },
    }
    requests_mock.get(
        f"https://api.github.com/repos/{owner}/{repo_slug}/git/refs/{ref}",
        json=expected_output,
    )
    result = client.get_ref(owner=owner, repo_slug=repo_slug, ref=ref)
    assert result == expected_output


@pytest.mark.xfail(reason="requests_mock fixture not working")
def test_get_tree(requests_mock):
    """Test the get_tree method of GitHubAPIClient."""
    client = GithubAPIClient()

    # Define sample input and output data
    client.owner = "my_username"
    client.repo_slug = "my_repo"
    tree_sha = "f7d5f10874c72632b919525d5dcb6b02705b2f56"
    expected_output = {
        "sha": tree_sha,
        "tree": [
            {
                "path": "file1.py",
            },
            {
                "path": "dir1",
            },
        ],
    }

    requests_mock.get(
        f"https://api.github.com/repos/{client.owner}/{client.repo_slug}/git/trees/{tree_sha}",
        json=expected_output,
    )
    result = client.get_tree(repo_slug=repo_slug, tree_sha=tree_sha)
    assert result == expected_output

    repo_slug = "my_other_repo"
    tree_sha = "f7d5f10874c72632b919525d5dcb6b02705b2f56"
    expected_output = {
        "sha": tree_sha,
        "url": f"https://api.github.com/repos/my_username/my_other_repo/git/trees/{tree_sha}",
        "tree": [
            {
                "path": "file1.py",
            },
            {
                "path": "dir1",
            },
        ],
    }
    requests_mock.get(
        f"https://api.github.com/repos/{client.owner}/{client.repo_slug}/git/trees/{tree_sha}",
        json=expected_output,
    )
    result = client.get_tree(repo_slug=None, tree_sha=tree_sha)
    assert result == expected_output


def test_get_api():
    result = get_api()
    assert isinstance(result, GhApi)


@pytest.mark.skip("The mock isn't working and is hitting the live API")
def test_get_user_by_username(github_api_get_user_by_username_response):
    api = get_api()
    with patch("libraries.github.get_user_by_username") as get_user_mock:
        get_user_mock.return_value = github_api_get_user_by_username_response
        result = get_user_by_username(api, "testerson")
        assert result == github_api_get_user_by_username_response
        assert "avatar_url" in result


# GithubUpdater tests


def test_update_issues_new(tp, library, github_api_repo_issues_response):
    """GithubUpdater.update_issues()"""
    new_issues_count = len(github_api_repo_issues_response)
    expected_count = Issue.objects.count() + new_issues_count
    with patch("libraries.github.repo_issues") as repo_issues_mock:
        updater = GithubUpdater(library=library)
        repo_issues_mock.return_value = github_api_repo_issues_response
        updater.update_issues()

    assert Issue.objects.count() == expected_count
    ids = [issue.id for issue in github_api_repo_issues_response]
    issues = Issue.objects.filter(library=library, github_id__in=ids)
    assert issues.exists()
    assert issues.count() == expected_count

    # Test the values of a sample Issue
    gh_issue = github_api_repo_issues_response[0]
    issue = issues.get(github_id=gh_issue.id)
    assert issue.title == gh_issue.title
    assert issue.number == gh_issue.number
    if gh_issue.state == "open":
        assert issue.is_open
    else:
        assert not issue.is_open
    assert issue.data == gh_issue

    expected_closed = parse(gh_issue["closed_at"])
    expected_created = parse(gh_issue["created_at"])
    expected_modified = parse(gh_issue["updated_at"])
    assert issue.closed == expected_closed
    assert issue.created == expected_created
    assert issue.modified == expected_modified


def test_update_issues_existing(tp, library, github_api_repo_issues_response):
    """Test that GithubUpdater.update_issues() updates existing issues when appropriate"""
    existing_issue_data = github_api_repo_issues_response[0]
    old_title = "Old title"
    issue = baker.make(
        Issue, library=library, github_id=existing_issue_data.id, title=old_title
    )

    # Make sure we are expected one fewer new issue, since we created one in advance
    new_issues_count = len(github_api_repo_issues_response)
    expected_count = Issue.objects.count() + new_issues_count - 1

    with patch("libraries.github.repo_issues") as repo_issues_mock:
        updater = GithubUpdater(library=library)
        repo_issues_mock.return_value = github_api_repo_issues_response
        updater.update_issues()

    assert Issue.objects.count() == expected_count
    ids = [issue.id for issue in github_api_repo_issues_response]
    issues = Issue.objects.filter(library=library, github_id__in=ids)
    assert issues.exists()
    assert issues.count() == expected_count

    # Test that the existing issue updated
    issue.refresh_from_db()
    assert issue.title == existing_issue_data.title


def test_update_issues_long_title(tp, library, github_api_repo_issues_response):
    """Test that GithubUpdater.update_issues() handles long title gracefully"""
    new_issues_count = len(github_api_repo_issues_response)
    expected_count = Issue.objects.count() + new_issues_count
    title = "sample" * 100
    assert len(title) > 255
    expected_title = title[:255]
    assert len(expected_title) <= 255

    with patch("libraries.github.repo_issues") as repo_issues_mock:
        updater = GithubUpdater(library=library)
        # Make an extra-long title so we can confirm that it saves
        github_id = github_api_repo_issues_response[0]["id"]
        github_api_repo_issues_response[0]["title"] = "sample" * 100
        repo_issues_mock.return_value = github_api_repo_issues_response
        updater.update_issues()

    assert Issue.objects.count() == expected_count
    assert Issue.objects.filter(library=library, github_id=github_id).exists()
    issue = Issue.objects.get(library=library, github_id=github_id)
    assert issue.title == expected_title


def test_update_prs_new(tp, library, github_api_repo_prs_response):
    """Test that GithubUpdater.update_prs() imports new PRs appropriately"""
    new_prs_count = len(github_api_repo_prs_response)
    expected_count = PullRequest.objects.count() + new_prs_count

    with patch("libraries.github.repo_prs") as repo_prs_mock:
        updater = GithubUpdater(library=library)
        github_api_repo_prs_response[0]["title"] = "sample" * 100
        repo_prs_mock.return_value = github_api_repo_prs_response
        updater.update_prs()

    assert PullRequest.objects.count() == expected_count
    ids = [pr.id for pr in github_api_repo_prs_response]
    pulls = PullRequest.objects.filter(library=library, github_id__in=ids)
    assert pulls.exists()
    assert pulls.count() == expected_count

    # Test the values of a sample PR
    gh_pull = github_api_repo_prs_response[0]
    pr = pulls.get(github_id=gh_pull.id)
    assert pr.title == gh_pull.title[:255]
    assert pr.number == gh_pull.number
    if gh_pull.state == "open":
        assert pr.is_open
    else:
        assert not pr.is_open
    assert pr.data == gh_pull

    expected_closed = parse(gh_pull["closed_at"])
    expected_created = parse(gh_pull["created_at"])
    expected_modified = parse(gh_pull["updated_at"])
    assert pr.closed == expected_closed
    assert pr.created == expected_created
    assert pr.modified == expected_modified


def test_update_prs_existing(tp, library, github_api_repo_prs_response):
    """Test that GithubUpdater.update_prs() updates existing PRs when appropriate"""
    existing_pr_data = github_api_repo_prs_response[0]
    old_title = "Old title"
    pull = baker.make(
        PullRequest, library=library, github_id=existing_pr_data.id, title=old_title
    )

    # Make sure we are expected one fewer new PRs, since we created one in advance
    new_prs_count = len(github_api_repo_prs_response)
    expected_count = PullRequest.objects.count() + new_prs_count - 1

    with patch("libraries.github.repo_prs") as repo_prs_mock:
        updater = GithubUpdater(library=library)
        repo_prs_mock.return_value = github_api_repo_prs_response
        updater.update_prs()

    assert PullRequest.objects.count() == expected_count
    ids = [pr.id for pr in github_api_repo_prs_response]
    pulls = PullRequest.objects.filter(library=library, github_id__in=ids)
    assert pulls.exists()
    assert pulls.count() == expected_count

    # Test that the existing PR updated
    pull.refresh_from_db()
    assert pull.title == existing_pr_data.title


# LibraryUpdater tests


def test_get_ref(github_api_get_ref_response):
    """LibraryUpdater.get_ref()"""
    with patch("libraries.github.LibraryUpdater.get_ref") as get_ref_mock:
        updater = LibraryUpdater()
        get_ref_mock.return_value = github_api_get_ref_response
        result = updater.get_ref(repo="boost", ref="heads/master")
        assert "object" in result


def test_get_boost_ref(tp, github_api_get_ref_response):
    """LibraryUpdater.get_boost_ref()"""
    with patch("libraries.github.LibraryUpdater.get_ref") as get_ref_mock:
        updater = LibraryUpdater()
        get_ref_mock.return_value = github_api_get_ref_response
        result = updater.get_boost_ref()
        assert "object" in result
        assert "url" in result
        assert "boostorg" in result["url"]


@responses.activate
def test_get_library_metadata(library_metadata):
    """LibraryUpdater.get_library_metadata()"""
    repo = "rational"
    url = (
        f"https://raw.githubusercontent.com/boostorg/{repo}/develop/meta/libraries.json"
    )
    responses.add(responses.GET, url, json=library_metadata)
    updater = LibraryUpdater()
    result = updater.get_library_metadata(repo)
    assert result == library_metadata


def test_get_library_github_data(github_api_get_repo_response):
    """LibraryUpdater.get_library_github_data(owner=owner, repo=repo)"""
    with patch("libraries.github.get_repo") as get_repo_mock:
        get_repo_mock.return_value = github_api_get_repo_response
        updater = LibraryUpdater()
        result = updater.get_library_github_data("owner", "repo")
        assert "updated_at" in result


def test_update_library(github_library):
    """LibraryUpdater.update_library()"""
    assert Library.objects.count() == 0
    updater = LibraryUpdater()
    updater.update_library(github_library)
    assert Library.objects.filter(name=github_library["name"]).exists()
    library = Library.objects.get(name=github_library["name"])
    assert library.github_url == github_library["github_url"]
    assert library.description == github_library["description"]
    assert library.cpp_standard_minimum == github_library["cxxstd"]
    assert library.categories.filter(name="sample1").exists()
    assert library.categories.filter(name="sample2").exists()


def test_update_categories(library):
    """LibraryUpdater.update_categories()"""
    assert library.categories.count() == 0
    updater = LibraryUpdater()
    updater.update_categories(library, ["sample1", "sample2"])
    library.refresh_from_db()
    assert library.categories.count() == 2
    assert library.categories.filter(name="sample1").exists()
    assert library.categories.filter(name="sample2").exists()
