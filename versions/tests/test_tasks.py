from datetime import datetime
from unittest.mock import MagicMock, patch
from libraries.models import LibraryVersion
from versions.models import Version
from versions.tasks import get_release_date_for_version, import_version, skip_tag
from libraries.management.commands.release_tasks import ReleaseTasksManager

import pytest


@pytest.fixture
def github_api_client():
    return MagicMock()


@pytest.mark.django_db
def test_get_release_date_for_version(version):
    """
    Test that the `get_release_date_for_version` task fetches and updates
    the release date.
    """
    commit_url = "https://api.github.com/repos/boostorg/boost/git/commits/some_sha"
    expected = datetime(2023, 1, 1).date()

    with patch(
        "core.githubhelper.GithubAPIClient.get_commit_by_sha"
    ) as mock_get_commit_by_sha:
        mock_get_commit_by_sha.return_value = {
            "committer": {"date": "2023-01-01T00:00:00Z"},
            "message": "some_message",
            "html_url": "some_url",
        }
        get_release_date_for_version(version.pk, commit_url)

    version.refresh_from_db()
    assert version.release_date == expected


def test_skip_tag(version):
    # Assert that existing tag names are skipped if new is True
    assert skip_tag(version.name, True) is True

    # Assert that existing tag names are not skipped if new is False
    assert skip_tag(version.name, False) is False

    # Assert that if it's on the exclusion list, it's skipped
    assert skip_tag("boost-beta-1.0") is True
    assert skip_tag("boost-1.25.1-bgl") is True

    # Assert that if the version is lower that the min, it's skipped
    assert skip_tag("boost-0.9.0") is True

    # Assert a random tag name is not skipped
    assert skip_tag("sample") is False


@pytest.mark.django_db
@patch("versions.tasks.import_library_versions")
@patch("versions.tasks.import_release_downloads")
def test_import_version_without_upsert(downloads_mock, library_versions_mock, version):
    """
    Regression test: when called with perform_upsert=False (as the
    import_versions release flow does), import_version must load the
    already-upserted Version instead of crashing on unbound locals.
    """
    import_version.run(
        name=version.name,
        tag={"name": version.name},
        perform_upsert=False,
    )
    downloads_mock.assert_called_once_with(version.pk)
    library_versions_mock.assert_called_once_with(version.name, token=None)


@pytest.mark.django_db
@patch("versions.tasks.import_version.run")
@patch("versions.tasks.import_release_notes.run")
@patch("versions.tasks.mark_fully_completed.run")
@patch("versions.tasks.GithubAPIClient.get_tags")
def test_import_version_race_condition(tag_mock: MagicMock, *args):
    """
    Test that when run synchronously the get_versions task does all deletion and creation
    of versions before returning
    """
    tag_mock.return_value = [{"name": "boost-1.91.0", "data": {}}]
    # This object is not competely imported, so should be deleted during import
    v, _ = Version.objects.with_partials().update_or_create(
        name="boost-1.91.0",
        defaults={
            "github_url": "",
            "beta": False,
            "full_release": True,
            "data": {},
        },
    )
    rm = ReleaseTasksManager("", "")
    # Ensure that a newly created manager has no latest version
    assert rm.latest_version is None
    rm.import_versions()
    # Ensure that we have a latest version
    assert rm.latest_version is not None
    # Ensure that that latest version is not our previously created version
    assert rm.latest_version != v


@patch("versions.tasks.call_command")
def test_import_reviews_task_backfills_the_review_source(mock_call):
    """Reviews are the only source of library-review, so this task owns it."""
    from versions.tasks import import_reviews_task

    import_reviews_task(actor_id=7)

    assert [c.args for c in mock_call.call_args_list] == [
        ("import_reviews",),
        ("backfill_achievements", "--source", "library-review"),
    ]
    # The admin who pressed the button, so the sync log can name them.
    assert mock_call.call_args_list[-1].kwargs == {"actor_id": 7}


@pytest.mark.django_db
@patch("versions.tasks.call_command")
@patch("versions.tasks.fetch_website_adoc_fields", return_value={})
@patch("versions.tasks.get_and_store_library_version_documentation_urls_for_version")
@patch("versions.tasks.GithubDataParser")
@patch("versions.tasks.LibraryUpdater")
@patch("versions.tasks.GithubAPIClient")
def test_import_library_versions_marks_a_failure_after_the_metadata_was_written(
    client_class,
    updater_class,
    parser_class,
    docs_mock,
    adoc_mock,
    call_command_mock,
    version,
):
    """The docs scrape runs last, and its failure has to be told from the others.

    ``synchronize_release_library_data`` tolerates a raise from here only when
    the library metadata it feeds to the author pass is already in place, and
    this exception is how it knows that. A release with no docs archive in S3 is
    the ordinary case: the rows are written, the scrape then raises.
    """
    from versions.exceptions import PostImportStepFailed
    from versions.tasks import import_library_versions

    parser_class.return_value.parse_gitmodules.return_value = [{"module": "array"}]
    parser_class.return_value.parse_libraries_json.return_value = {
        "key": "array",
        "name": "Array",
        "authors": ["Nicolai Josuttis"],
        "cpp20_module_support": False,
    }
    client_class.return_value.get_repo.return_value = {
        "html_url": "https://github.com/boostorg/array"
    }
    updater_class.return_value.skip_modules = []
    updater_class.return_value.skip_libraries = []
    docs_mock.side_effect = ValueError("Could not get content from S3")

    with pytest.raises(PostImportStepFailed) as raised:
        import_library_versions(version.name)

    # The keys it read, so the caller can still tell an import that read nothing.
    assert raised.value.library_keys == ["array"]
    assert LibraryVersion.objects.filter(version=version, library__key="array").exists()
    # The maintainers pass belongs to the same tail and never ran.
    assert call_command_mock.call_args_list == []
