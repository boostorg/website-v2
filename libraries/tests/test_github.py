import datetime
from unittest.mock import call, MagicMock, patch

import pytest
import responses
from ghapi.all import GhApi
from model_bakery import baker

from libraries.github import GithubAPIClient, GithubDataParser, LibraryUpdater
from libraries.models import Category, Issue, Library, PullRequest

"""GithubAPIClient Tests"""


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


###########################################################################
# Something is up with this test, it causes Pytest to fail spectacularly
# using Python 3.11.  Commenting it out for now.  - Frank
###########################################################################
# @pytest.mark.xfail(reason="Something up with bytes")
# @responses.activate
# def test_get_gitmodules(github_api_client):
#     """Test the get_gitmodules method of GitHubAPIClient."""
#     sample_ref_response = {
#         "object": {
#             "sha": "12345",
#         }
#     }
#     sample_tree_response = {
#         "tree": [
#             {
#                 "path": ".gitmodules",
#                 "sha": "67890",
#             }
#         ]
#     }

#     sample_content = "sample content"
#     sample_blob_response = {
#         "content": base64.b64encode(sample_content.encode("utf-8")).decode("utf-8")
#     }

#     # Set up the mocked API responses
#     ref_url = f"https://api.github.com/repos/{github_api_client.owner}/{github_api_client.repo_slug}/git/ref/{github_api_client.ref}"
#     tree_url = f"https://api.github.com/repos/{github_api_client.owner}/{github_api_client.repo_slug}/git/trees/12345"

#     responses.add(responses.GET, ref_url, json=sample_ref_response, status=200)
#     responses.add(responses.GET, tree_url, json=sample_tree_response, status=200)

#     # Mock the get_blob method
#     github_api_client.get_blob = MagicMock(return_value=sample_blob_response)

#     # Call the get_gitmodules method
#     result = github_api_client.get_gitmodules(repo_slug="sample_repo")

#     # Assert the expected result
#     assert result == sample_content

#     # Check if the API calls were made with the correct arguments
#     assert len(responses.calls) == 2
#     assert responses.calls[0].request.url == ref_url
#     assert responses.calls[1].request.url == tree_url
#     github_api_client.get_blob.assert_called_with(
#         repo_slug="sample_repo", file_sha="67890"
#     )


@pytest.mark.skip(reason="Mocking the API is not working")
def test_get_first_tag(github_api_client, mock_api):
    """Test the get_first_tag method of GithubAPIClient."""

    # Mock tags from the GitHub API
    mock_tags = [
        {"name": "tag2", "commit": {"sha": "2"}},
        {"name": "tag1", "commit": {"sha": "1"}},
    ]

    # Mock the commit data from the GitHub API
    mock_commits = [
        {"sha": "2", "committer": {"date": "2023-05-12T00:00:00Z"}},
        {"sha": "1", "committer": {"date": "2023-05-11T00:00:00Z"}},
    ]

    # Setup the mock API to return the mock tags and commits
    github_api_client.api.repos.list_tags.side_effect = MagicMock(
        return_value=mock_tags
    )
    github_api_client.api.git.get_commit.side_effect = MagicMock(
        return_value=mock_commits
    )
    repo_slug = "sample_repo"
    tag = github_api_client.get_first_tag(repo_slug=repo_slug)

    # Assert that the earliest tag was returned
    assert tag == (mock_tags[1], "2000-01-01T00:00:00Z")


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


def test_parse_tag():
    commit_data = {
        "commit": {
            "author": {"date": "2023-05-10T00:00:00Z"},
            "message": "This is a sample description for a commit",
        },
        "html_url": "http://example.com/commit/12345",
    }
    expected = {
        "release_date": datetime.date(2023, 5, 10),
        "description": "This is a sample description for a commit",
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


"""LibraryUpdater Tests"""


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
            "last_github_update": None,
            "category": ["Test"],
            "authors": ["John Doe"],
            "maintainers": ["Jane Doe"],
        }
    ]
    result = library_updater.get_library_list(gitmodules=gitmodules)
    assert result == expected


def test_get_library_list_skip(library_updater):
    """Test that the get_library_list method of LibraryUpdater skips the right modules"""
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
                "last_github_update": None,
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
        "last_github_update": None,
        "category": ["Test"],
        "authors": ["John Doe"],
        "maintainers": ["Jane Doe"],
    }
    library_updater.update_library(library_data)
    assert Library.objects.filter(key="test").exists()
    library = Library.objects.get(key="test")
    assert library.categories.filter(name="Test").exists()


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
