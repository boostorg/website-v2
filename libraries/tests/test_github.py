from unittest.mock import patch

import pytest
import responses
from dateutil.parser import parse
from ghapi.all import GhApi
from model_bakery import baker

from libraries.github import GithubUpdater, LibraryUpdater, get_api
from libraries.models import Issue, Library


def test_get_api():
    result = get_api()
    assert isinstance(result, GhApi)


# GithubUpdater tests
@pytest.mark.skip(reason="Method not yet written")
def test_update_prs():
    pass


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
    """GithubUpdater.update_issues()"""
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
    """GithubUpdater.update_issues()"""
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
