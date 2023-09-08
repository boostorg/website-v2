import datetime
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


def test_library_version_first_boost_version_property(library):
    # Test for a library with no library versions
    assert library.first_boost_version is None

    # Test for a library with multiple versions, each with a different release_date
    version_1 = baker.make(
        "versions.Version", name="1.0", release_date=datetime.date(2023, 1, 1)
    )
    version_2 = baker.make(
        "versions.Version", name="1.1", release_date=datetime.date(2023, 1, 2)
    )
    version_3 = baker.make(
        "versions.Version", name="1.2", release_date=datetime.date(2023, 1, 3)
    )

    baker.make("libraries.LibraryVersion", library=library, version=version_1)
    baker.make("libraries.LibraryVersion", library=library, version=version_2)
    baker.make("libraries.LibraryVersion", library=library, version=version_3)
    del library.first_boost_version
    assert library.first_boost_version == version_1

    # Test for a library with multiple versions, released on the same date, but
    # with version names that increment appropriately
    version_1.release_date = datetime.date(2023, 1, 1)
    version_1.save()
    version_2.release_date = datetime.date(2023, 1, 1)
    version_2.save()
    version_3.release_date = datetime.date(2023, 1, 1)
    version_3.save()
    del library.first_boost_version
    assert library.first_boost_version == version_1

    # Test for a library with multiple versions, released on different date, but
    # with version names that increment oddly
    version_1.release_date = datetime.date(2023, 2, 1)
    version_1.save()
    version_2.release_date = datetime.date(2023, 4, 1)
    version_2.save()
    version_3.release_date = datetime.date(2023, 1, 1)
    version_3.save()
    del library.first_boost_version
    assert library.first_boost_version == version_3
