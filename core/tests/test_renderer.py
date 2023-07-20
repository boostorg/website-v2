from unittest.mock import Mock, patch
import datetime
from io import BytesIO
import pytest

from ..boostrenderer import (
    extract_file_data,
    get_body_from_html,
    get_content_type,
    get_file_data,
    get_s3_keys,
)


@pytest.fixture
def mock_s3_client():
    return "mock_s3_client"


def test_extract_file_data():
    response = {
        "Body": BytesIO(b"file content"),
        "ContentType": "text/plain",
        "LastModified": datetime.datetime(2023, 6, 8, 12, 0, 0),
    }
    s3_key = "example_key.txt"

    expected_result = {
        "content": b"file content",
        "content_key": s3_key,
        "content_type": "text/plain",
        "last_modified": datetime.datetime(2023, 6, 8, 12, 0, 0),
    }

    result = extract_file_data(response, s3_key)

    assert result == expected_result


def test_get_body_from_html():
    html_string = (
        "<html><head><title>Test</title></head><body><h1>Test</h1></body></html>"
    )
    body_content = get_body_from_html(html_string)
    assert body_content == "<h1>Test</h1>"


def test_get_body_from_html_strip_footer():
    html_string = """
    <html>
        <head><title>Test</title></head>
        <body>
            <h1>Test</h1>
            <div id='footer'>Some content</div>
            <span id='contains-footer'>More content</span>
        </body>
    </html>
    """
    body_content = get_body_from_html(html_string)
    assert body_content == "<h1>Test</h1>"


def test_get_content_type():
    # HTML file content type is text/html
    assert get_content_type("/marshmallow/index.html", "text/html"), "text/html"

    # CSS file content type is text/css
    assert get_content_type("/rst.css", "text/css"), "text/css"

    # Asciidoc content, which comes from S3 with an .adoc extension but not a useful
    # content type, should be changed to text/asciidoc
    assert get_content_type("/site/develop/help.adoc", "text/html"), "text/asciidoc"

    # JS file content type is always set to application/javascript
    assert get_content_type(
        "/site/develop/doc/html/scripts.js", "text/html"
    ), "application/javascript"


def test_get_file_data():
    # Mock the S3 client
    mock_client = Mock()
    mock_response = Mock()
    mock_extract_file_data = Mock(return_value="mock_file_data")

    # Patch the necessary functions and objects
    with patch("core.boostrenderer.extract_file_data", mock_extract_file_data), patch(
        "core.boostrenderer.logger"
    ) as mock_logger:
        # Set up the mock response
        mock_client.get_object.return_value = mock_response

        bucket_name = "my-bucket"
        s3_key = "/path/to/file.txt"

        expected_result = "mock_file_data"

        # Call the function being tested
        result = get_file_data(mock_client, bucket_name, s3_key)

        # Assert the expected behavior and result
        assert result == expected_result
        mock_client.get_object.assert_called_once_with(
            Bucket=bucket_name, Key=s3_key.lstrip("/")
        )
        mock_extract_file_data.assert_called_once_with(mock_response, s3_key)
        assert not mock_logger.exception.called


def test_get_s3_keys():
    """
    Test cases:

    - "/marshmallow/index.html" -> "site/develop/tools/auto_index/index.html"
    - "/marshmallow/about.html" -> "site/develop/doc/html/about.html"
    - "/rst.css" -> "site/develop/rst.css"
    - "/site/develop/doc/html/about.html" -> "site/develop/doc/html/about.html"
    """

    assert "/site-docs/develop/user-guide/index.html" in get_s3_keys(
        "/doc/user-guide/index.html"
    )
    assert "/site-docs/develop/contributor-guide/index.html" in get_s3_keys(
        "/doc/contributor-guide/index.html"
    )
    assert "/site-docs/develop/formal-reviews/index.html" in get_s3_keys(
        "/doc/formal-reviews/index.html"
    )
    assert "/site-docs/develop/release-process/index.html" in get_s3_keys(
        "/doc/release-process/index.html"
    )
