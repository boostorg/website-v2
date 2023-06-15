import pytest
from model_bakery import baker


def test_get_cpp_standard_minimum_display(library):
    library.cpp_standard_minimum = "11"
    library.save()
    assert library.get_cpp_standard_minimum_display() == "C++11"

    library.cpp_standard_minimum = "42"
    library.save()
    assert library.get_cpp_standard_minimum_display() == "42"


def test_github_properties(library):
    properties = library.github_properties()
    assert properties["owner"] == "boostorg"
    assert properties["repo"] == "multi_array"


def test_github_owner(library):
    assert library.github_owner == "boostorg"


def test_github_repo(library):
    assert library.github_repo == "multi_array"


def test_get_issues_link(library):
    result = library.github_issues_url
    expected = f"https://github.com/{library.github_owner}/{library.github_repo}/issues"
    assert expected == result


def test_category_creation(category):
    assert category.name is not None


def test_commit_data_creation(commit_data):
    assert commit_data.commit_count > 0


def test_library_creation(library):
    assert library.versions.count() == 0


def test_issue_creation(issue, library):
    assert issue.library == library


def test_pull_request_creation(pull_request, library):
    assert pull_request.library == library


def test_library_version_creation(library_version, library, version):
    assert library_version.library == library
    assert library_version.version == version


def test_library_version_str(library_version, library, version):
    assert str(library_version) == f"{library.name} ({version.name})"


def test_library_version_multiple_versions(library, library_version):
    assert library.versions.count() == 1
    assert library.versions.filter(
        library_version__version=library_version.version
    ).exists()
    other_version = baker.make("versions.Version", name="New Version")
    baker.make("libraries.LibraryVersion", library=library, version=other_version)
    assert library.versions.count() == 2
    assert library.versions.filter(
        library_version__version=library_version.version
    ).exists()
    assert library.versions.filter(library_version__version=other_version).exists()


def test_library_repo_url_for_version(library_version):
    result = library_version.library_repo_url_for_version
    expected_url = (
        f"{library_version.library.github_url}/tree/{library_version.version.name}"
    )
    assert result == expected_url


def test_library_repo_url_for_version_invalid_data(library_version):
    version = library_version.version
    library = library_version.library

    library_version.version = None
    library_version.save()

    with pytest.raises(ValueError):
        library_version.library_repo_url_for_version

    library_version.version = version
    library_version.library = None
    library_version.save()

    with pytest.raises(ValueError):
        library_version.library_repo_url_for_version

    library_version.library = library
    library_version.library.github_url = None
    library_version.library.save()

    with pytest.raises(ValueError):
        library_version.library_repo_url_for_version
        
def test_library_version_documentation_url(library_version):
    library_version.version.slug = "boost-1.82.0"
    library_version.version.save()
    version = library_version.version
    library = library_version.library
    version_slug = version.boost_url_slug
    lib_slug = library.key
    expected = f"https://www.boost.org/doc/libs/{version_slug}/libs/{lib_slug}/"
    assert library_version.documentation_url == expected
