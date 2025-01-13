import datetime
from django.db.models import Sum
from model_bakery import baker

from libraries.models import CommitAuthor
from mailing_list.models import EmailData


def test_get_cpp_standard_minimum_display(library_version):
    library_version.cpp_standard_minimum = "11"
    library_version.save()
    assert library_version.get_cpp_standard_minimum_display() == "C++11"

    library_version.cpp_standard_minimum = "42"
    library_version.save()
    assert library_version.get_cpp_standard_minimum_display() == "42"


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


def test_get_issues_link_override():
    outcome_library = baker.make(
        "libraries.Library",
        name="Outcome",
        slug="outcome",
        github_url="https://github.com/boostorg/outcome",
    )
    expected = "https://github.com/ned14/outcome/issues"
    assert outcome_library.github_issues_url == expected


def test_category_creation(category):
    assert category.name is not None


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


def test_merge_author_deletes_author():
    author_1_email = baker.make("libraries.CommitAuthorEmail")
    author_1 = author_1_email.author
    author_2_email = baker.make("libraries.CommitAuthorEmail")
    author_2 = author_2_email.author

    assert CommitAuthor.objects.count() == 2
    author_1.merge_author(author_2)
    assert CommitAuthor.objects.all().get() == author_1
    assert author_1.commitauthoremail_set.count() == 2


def test_merge_author_reassigns_commits():
    lv = baker.make("libraries.LibraryVersion")
    author_1 = baker.make("libraries.CommitAuthor")
    author_2 = baker.make("libraries.CommitAuthor")
    author_3 = baker.make("libraries.CommitAuthor")

    for author in [author_1, author_2, author_3]:
        baker.make("libraries.Commit", author=author, library_version=lv, _quantity=10)

    assert author_1.commit_set.count() == 10
    author_1.merge_author(author_2)
    assert author_1.commit_set.count() == 20


def test_merge_author_reassigns_emaildata():
    versions = []
    for i in range(10):
        versions.append(
            baker.make(
                "versions.Version", name=f"0.{i}.0", release_date=f"{2000 + i}-01-01"
            )
        )

    authors = baker.make("libraries.CommitAuthor", _quantity=10)
    for author in authors:
        for version in versions:
            baker.make(
                "mailing_list.EmailData", author=author, version=version, count=10
            )

    assert EmailData.objects.all().aggregate(total=Sum("count"))["total"] == 1000
    assert sum(authors[0].emaildata_set.all().values_list("count", flat=True)) == 100

    authors[0].merge_author(authors[1])

    # all of author[1]'s emaildata counts should go to author[0]
    assert sum(authors[0].emaildata_set.all().values_list("count", flat=True)) == 200
    # total should stay the same
    assert EmailData.objects.all().aggregate(total=Sum("count"))["total"] == 1000
