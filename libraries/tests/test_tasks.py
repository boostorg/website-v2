import pytest
from unittest.mock import MagicMock, patch

from libraries.tasks import (
    get_and_store_library_version_documentation_urls_for_version,
    library_version_missing_docs,
    version_missing_docs,
)


@pytest.fixture
def mock_s3_client():
    return MagicMock()


@patch("core.boostrenderer.get_s3_client")
def test_get_and_store_library_version_documentation_urls_for_version(
    mock_get_s3_client, library_version, mock_s3_client, tp
):
    mock_get_s3_client.return_value = mock_s3_client
    version = library_version.version
    library = library_version.library
    library_name = library.name.lower()
    mock_s3_response = {"content": f"""
        <h2>Libraries Listed <a name="Alphabetically">Alphabetically</a></h2>
        <ul>
            <li><a href="{library_name}/index.html">{library_name}</a></li>
        </ul>
    """}

    # Mock the get_content_from_s3 function to return the mock S3 response
    mock_s3_client.get_object.return_value = mock_s3_response

    with patch(
        "core.boostrenderer.get_file_data", return_value=mock_s3_response
    ) as mock_get_file_data:
        get_and_store_library_version_documentation_urls_for_version(version.pk)
        mock_get_file_data.assert_called_once()

    # Refresh the library_version object from the database
    library_version.refresh_from_db()
    # Assert that the docs_path was updated as expected
    slug = version.boost_url_slug.replace("boost_", "")
    assert (
        library_version.documentation_url
        == f"/doc/libs/{slug}/libs/{library_name}/index.html"
    )


@patch("core.boostrenderer.get_s3_client")
def test_get_and_store_library_version_documentation_urls_for_version_no_content(
    mock_get_s3_client, library_version, mock_s3_client, tp
):
    mock_get_s3_client.return_value = mock_s3_client
    version = library_version.version
    library = library_version.library
    old_documentation_url = library_version.documentation_url
    library.name.lower()
    mock_s3_response = None

    # Mock the get_content_from_s3 function to return the mock S3 response
    mock_s3_client.get_object.return_value = mock_s3_response

    with patch(
        "core.boostrenderer.get_file_data", return_value=mock_s3_response
    ), pytest.raises(ValueError):
        get_and_store_library_version_documentation_urls_for_version(version.pk)

    library_version.refresh_from_db()
    assert library_version.documentation_url == old_documentation_url


@pytest.mark.parametrize(
    "library_slug, version_name, expected_result",
    [
        ("detail", "boost-1.59.0", True),  # Older than max_version
        ("exception", "boost-1.36.0", False),  # Newer than max_version
        ("graphparallel", "boost-1.35.0", True),  # Within the missing range
        ("graphparallel", "boost-1.40.0", False),  # Outside the missing range
        ("log", "boost-1.54.0", False),  # Newer than max_version
        ("nonexistent", "boost-1.60.0", False),  # Library not in the dictionary
    ],
)
def test_library_version_missing_docs(
    library_version, library_slug, version_name, expected_result
):
    library_version.library.slug = library_slug
    library_version.library.save()
    library_version.version.name = version_name
    library_version.version.save()
    library_version.refresh_from_db()

    assert library_version_missing_docs(library_version) == expected_result


@pytest.mark.parametrize(
    "version_name, expected",
    [
        ("boost-1.33.0", True),  # Version explicitly listed in VERSION_DOCS_MISSING
        ("boost-1.30.0", True),  # Version older than the oldest in S3
        (
            "boost-1.32.0",
            False,
        ),  # Version newer than the oldest in S3 and not listed in VERSION_DOCS_MISSING
    ],
)
def test_version_missing_docs(version, version_name, expected):
    version.name = version_name
    version.save()
    result = version_missing_docs(version)
    assert result == expected


@patch("libraries.tasks.call_command")
def test_update_authors_and_maintainers_backfills_only_library_sources(mock_call):
    """A blanket backfill here would sweep the commit, review and news tables."""
    from libraries.tasks import update_authors_and_maintainers

    update_authors_and_maintainers()

    backfills = [
        c for c in mock_call.call_args_list if c.args[0] == "backfill_achievements"
    ]
    assert len(backfills) == 1
    assert set(backfills[0].args[1:]) == {
        "--source",
        "library-authoring",
        "library-maintenance",
        "library-versioning",
    }


@patch("libraries.tasks.LibraryUpdater")
@patch("libraries.tasks.call_command")
def test_update_commits_does_not_backfill(mock_call, _mock_updater, db):
    """release_tasks sweeps every source once; a call here would double it."""
    from libraries.tasks import update_commits

    update_commits()

    assert not [
        c for c in mock_call.call_args_list if c.args[0] == "backfill_achievements"
    ]


@patch("libraries.tasks.call_command")
def test_release_tasks_delegates_the_backfill_to_the_command(mock_call):
    """The sweep is an Action inside release_tasks, not a trailing extra call."""
    from libraries.management.commands.release_tasks import ReleaseTasksManager
    from libraries.tasks import release_tasks

    release_tasks("https://example.com")

    assert [c.args[0] for c in mock_call.call_args_list] == ["release_tasks"]
    manager = ReleaseTasksManager(base_uri="https://example.com", user_id=None)
    assert [
        task.description
        for task in manager.tasks
        if task.handler == ["backfill_achievements"]
    ] == ["Backfilling achievements"]
