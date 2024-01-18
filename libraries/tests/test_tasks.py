import pytest
from unittest.mock import MagicMock, patch

from libraries.tasks import get_and_store_library_version_documentation_urls_for_version


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
    mock_s3_response = {
        "content": f"""
        <h2>Libraries Listed <a name="Alphabetically">Alphabetically</a></h2>
        <ul>
            <li><a href="{library_name}/index.html">{library_name}</a></li>
        </ul>
    """
    }

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
    assert (
        library_version.documentation_url
        == f"/doc/libs/{version.boost_url_slug}/libs/{library_name}/index.html"
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
