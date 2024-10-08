from unittest.mock import patch

from core.asciidoc import convert_adoc_to_html


def test_convert_adoc_to_html_subprocess():
    # The content of the sample adoc file
    sample_adoc_content = "= Document Title\n\nThis is a sample document.\n"

    # Execute the task
    with patch("core.asciidoc.subprocess.run") as mock_run:
        mock_run.return_value.stdout = "html_content"
        result = convert_adoc_to_html(sample_adoc_content)
    assert result == "html_content"


def test_convert_adoc_to_html_content():
    """Test the process_adoc_to_html_content function."""
    content = "sample"
    expected_html = '<div class="paragraph">\n<p>sample</p>\n</div>\n'  # noqa: E501

    result = convert_adoc_to_html(content)
    assert result == expected_html
