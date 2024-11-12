from os import getcwd, makedirs
from unittest.mock import patch

import pytest


from core.asciidoc import convert_adoc_to_html


def test_convert_adoc_to_html_subprocess():
    # The content of the sample adoc file
    sample_adoc_content = "= Document Title\n\nThis is a sample document.\n"

    # Execute the task
    with patch("core.asciidoc.subprocess.run") as mock_run:
        mock_run.return_value.stdout = "html_content"
        result = convert_adoc_to_html(sample_adoc_content)
    assert result == "html_content"


@pytest.mark.asciidoctor
def test_convert_adoc_to_html_content():
    """Test the process_adoc_to_html_content function."""
    content = "sample"
    expected_html = '<div class="paragraph">\n<p>sample</p>\n</div>\n'  # noqa: E501

    result = convert_adoc_to_html(content)
    assert result == expected_html


@pytest.mark.asciidoctor
def test_convert_adoc_to_html_content_file():
    # for dev, change this to True, and update the test_pytest_asciidoctor run
    #  command to include "-v /tmp/asciidocs:/tmp/asciidocs" after "run"
    generate_files_for_debugging = False
    expected_output = open(f"{getcwd()}/core/tests/content/asciidoc.html").read()
    adoc_file_path = f"{getcwd()}/core/tests/content/asciidoc.adoc"
    output = convert_adoc_to_html(open(adoc_file_path).read())
    if generate_files_for_debugging:
        makedirs("/tmp/asciidocs", exist_ok=True)
        open("/tmp/asciidocs/tmp.html", "w").write(output)
    assert output == expected_output
