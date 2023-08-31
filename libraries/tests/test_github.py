import datetime
from unittest.mock import MagicMock, patch

import pytest
from ghapi.all import GhApi
from model_bakery import baker

from libraries.github import LibraryUpdater
from core.githubhelper import GithubAPIClient
from libraries.models import Category, Issue, Library, PullRequest


@pytest.fixture
def github_api_client():
    return GithubAPIClient()


@pytest.fixture(scope="function")
def mock_api() -> GhApi:
    """Fixture that mocks the GitHub API."""
    with patch("libraries.github.GhApi") as mock_api_class:
        yield mock_api_class.return_value


@pytest.fixture
def github_api_client_mock():
    """ """
    mock = MagicMock()
    return mock


@pytest.fixture
def mock_gh_api_client():
    client = GithubAPIClient()
    client.get_libraries_json = MagicMock(return_value=None)
    client.get_repo = MagicMock(return_value=None)
    client.get_gitmodules = MagicMock(return_value=b"sample content")
    return client


@pytest.fixture
def library_updater(mock_gh_api_client):
    return LibraryUpdater()


def test_get_library_list(library_updater):
    """Test the get_library_list method of LibraryUpdater."""
    gitmodules = [{"module": "test"}]
    library_updater.client.get_libraries_json = MagicMock(
        return_value=[
            {
                "key": "test",
                "name": "Test Library",
                "description": "Test description",
                "cxxstd": "11",
                "category": ["Test"],
                "authors": ["John Doe"],
                "maintainers": ["Jane Doe"],
            }
        ]
    )
    library_updater.client.get_repo = MagicMock(
        return_value={"html_url": "example.com"}
    )
    expected = [
        {
            "key": "test",
            "name": "Test Library",
            "github_url": "example.com",
            "description": "Test description",
            "cxxstd": "11",
            "category": ["Test"],
            "authors": ["John Doe"],
            "maintainers": ["Jane Doe"],
        }
    ]
    result = library_updater.get_library_list(gitmodules=gitmodules)
    assert result == expected


def test_get_library_list_skip(library_updater):
    """Test that get_library_list method of LibraryUpdater skips the right modules"""
    gitmodules = [{"module": "litre"}]
    result = library_updater.get_library_list(gitmodules=gitmodules)
    assert result == []


def test_update_authors(library_updater, user, library_version):
    library = library_version.library
    assert library.authors.exists() is False
    user.claimed = True
    user.email = "t_testerson@example.com"
    user.save()

    library_updater.update_authors(
        library,
        authors=[
            "Tester Testerston <t_testerson -at- example.com>",
            "Tester2 Testerson2",
        ],
    )
    library.refresh_from_db()
    assert library.authors.exists()
    assert library.authors.filter(email="t_testerson@example.com").exists()
    assert library.authors.filter(email="tester2_testerson2@example.com").exists()


def test_update_maintainers(library_updater, user, library_version):
    assert library_version.maintainers.exists() is False
    user.claimed = True
    user.email = "t_testerson@example.com"
    user.save()

    library_updater.update_maintainers(
        library_version,
        maintainers=[
            "Tester Testerston <t_testerson -at- example.com>",
            "Tester2 Testerson2",
        ],
    )
    library_version.refresh_from_db()
    assert library_version.maintainers.exists()
    assert library_version.maintainers.filter(email="t_testerson@example.com").exists()
    assert library_version.maintainers.filter(
        email="tester2_testerson2@example.com"
    ).exists()


@pytest.mark.skip("Needs API mocking")
def test_update_monthly_commit_counts(library_version, library_updater):
    # Assert no current data
    assert library_version.library.commit_data.exists() is False

    {
        datetime.date(2023, 1, 1): 2,
        datetime.date(2023, 2, 1): 3,
        datetime.date(2023, 3, 1): 1,
    }
    library_updater.update_monthly_commit_counts(library_version.library, branch="main")
    assert library_version.library.commit_data.exists() is True
    assert library_version.library.commit_data.count() == 3
    assert library_version.library.commit_data.filter(
        month_year=datetime.date(2023, 1, 1), commit_count=2
    ).exists()
    assert library_version.library.commit_data.filter(
        month_year=datetime.date(2023, 2, 1), commit_count=3
    ).exists()
    assert library_version.library.commit_data.filter(
        month_year=datetime.date(2023, 3, 1), commit_count=1
    ).exists()


@pytest.mark.skip("Add this test when we have figured out GH API mocking")
def test_update_libraries(library_updater, version):
    """Test the update_libraries method of LibraryUpdater."""
    assert Library.objects.filter(key="test").exists() is False
    library_updater.parser.parse_gitmodules = MagicMock(return_value=[])
    library_updater.get_library_list = MagicMock(
        return_value=[
            {
                "key": "test",
                "name": "Test Library",
                "github_url": "https://github.com/test/test",
                "description": "Test description",
                "cxxstd": "11",
                "category": ["Test"],
                "authors": ["John Doe"],
                "maintainers": ["Jane Doe"],
            }
        ]
    )
    library_updater.update_libraries()
    assert Library.objects.filter(key="test").exists()


def test_update_library(library_updater, version):
    """Test the update_library method of LibraryUpdater."""
    assert Library.objects.filter(key="test").exists() is False
    library_data = {
        "key": "test",
        "name": "Test Library",
        "github_url": "https://github.com/test/test",
        "description": "Test description",
        "cxxstd": "11",
        "category": ["Test"],
        "authors": ["John Doe"],
        "maintainers": ["Jane Doe"],
    }
    library_updater.update_library(library_data)
    assert Library.objects.filter(key="test").exists()
    Library.objects.get(key="test")


def test_update_categories(library, library_updater):
    """Test the update_categories method of LibraryUpdater."""
    assert Category.objects.filter(name="Test").exists() is False
    assert library.categories.filter(name="Test").exists() is False
    library_updater.update_categories(library, ["Test"])
    library.refresh_from_db()
    assert Category.objects.filter(name="Test").exists()
    assert library.categories.filter(name="Test").exists()


def test_update_issues_new(
    tp, library, github_api_repo_issues_response, library_updater
):
    """Test the update_issues method of LibraryUpdater with new issues."""
    new_issues_count = len(github_api_repo_issues_response)
    expected_count = Issue.objects.count() + new_issues_count
    library_updater.client.get_repo_issues = MagicMock(
        return_value=github_api_repo_issues_response
    )
    library_updater.update_issues(library)

    ids = [issue.id for issue in github_api_repo_issues_response]
    issues = Issue.objects.filter(library=library, github_id__in=ids)
    assert Issue.objects.filter(library=library, github_id__in=ids).exists()
    assert (
        Issue.objects.filter(library=library, github_id__in=ids).count()
        == expected_count
    )

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


def test_update_issues_existing(
    tp, library, github_api_repo_issues_response, library_updater
):
    """Test the update_issues method of LibraryUpdater with existing issues."""
    existing_issue_data = github_api_repo_issues_response[0]
    old_title = "Old title"
    issue = baker.make(
        Issue, library=library, github_id=existing_issue_data.id, title=old_title
    )

    # Make sure we are expected one fewer new issue, since we created one in advance
    new_issues_count = len(github_api_repo_issues_response)
    expected_count = Issue.objects.count() + new_issues_count - 1

    library_updater.client.get_repo_issues = MagicMock(
        return_value=github_api_repo_issues_response
    )
    library_updater.update_issues(library)

    assert Issue.objects.count() == expected_count
    ids = [issue.id for issue in github_api_repo_issues_response]
    issues = Issue.objects.filter(library=library, github_id__in=ids)
    assert issues.exists()
    assert issues.count() == expected_count

    # Test that the existing issue updated
    issue.refresh_from_db()
    assert issue.title == existing_issue_data.title


def test_update_issues_long_title(
    tp, library, github_api_repo_issues_response, library_updater
):
    """Test the update_issues method of LibraryUpdater handles long title gracefully"""
    new_issues_count = len(github_api_repo_issues_response)
    expected_count = Issue.objects.count() + new_issues_count
    title = "sample" * 100
    assert len(title) > 255
    expected_title = title[:255]
    assert len(expected_title) <= 255

    github_id = github_api_repo_issues_response[0]["id"]
    github_api_repo_issues_response[0]["title"] = "sample" * 100
    library_updater.client.get_repo_issues = MagicMock(
        return_value=github_api_repo_issues_response
    )
    library_updater.update_issues(library)

    assert Issue.objects.count() == expected_count
    assert Issue.objects.filter(library=library, github_id=github_id).exists()
    issue = Issue.objects.get(library=library, github_id=github_id)
    assert issue.title == expected_title


def test_update_prs_new(tp, library, github_api_repo_prs_response, library_updater):
    """Test that LibraryUpdater.update_prs() imports new PRs appropriately"""
    new_prs_count = len(github_api_repo_prs_response)
    expected_count = PullRequest.objects.count() + new_prs_count

    github_api_repo_prs_response[0]["title"] = "sample" * 100
    library_updater.client.get_repo_prs = MagicMock(
        return_value=github_api_repo_prs_response
    )
    library_updater.update_prs(library)

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


def test_update_prs_existing(
    tp, library, github_api_repo_prs_response, library_updater
):
    """Test that LibraryUpdater.update_prs() updates existing PRs when appropriate"""
    existing_pr_data = github_api_repo_prs_response[0]
    old_title = "Old title"
    pull = baker.make(
        PullRequest, library=library, github_id=existing_pr_data.id, title=old_title
    )

    # Make sure we are expected one fewer new PRs, since we created one in advance
    new_prs_count = len(github_api_repo_prs_response)
    expected_count = PullRequest.objects.count() + new_prs_count - 1

    library_updater.client.get_repo_prs = MagicMock(
        return_value=github_api_repo_prs_response
    )
    library_updater.update_prs(library)

    assert PullRequest.objects.count() == expected_count
    ids = [pr.id for pr in github_api_repo_prs_response]
    pulls = PullRequest.objects.filter(library=library, github_id__in=ids)
    assert pulls.exists()
    assert pulls.count() == expected_count

    # Test that the existing PR updated
    pull.refresh_from_db()
    assert pull.title == existing_pr_data.title
