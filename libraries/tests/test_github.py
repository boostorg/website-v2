from unittest.mock import patch

import responses
from ghapi.all import GhApi

from libraries.github import LibraryUpdater, get_api
from libraries.models import Library


def test_get_api():
    result = get_api()
    assert isinstance(result, GhApi)


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
