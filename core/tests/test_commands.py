import pytest
from django.core import management
from django.conf import settings
import os


@pytest.fixture
def cleanup_test_asciidoc():
    # This function will be executed after the test function completes
    def remove_files():
        for extension in ("adoc", "html"):
            expected_output_file = f"core/tests/sample.{extension}"
            os.remove(os.path.join(settings.BASE_DIR, expected_output_file))

    # Yield control back to the test function
    yield
    # After the test function completes, execute the cleanup
    remove_files()


@pytest.mark.django_db
def test_asciidoc_command_creates_output(cleanup_test_asciidoc):
    input_file = "core/tests/sample.adoc"
    output_file = "core/tests/sample.html"

    # Create a test AsciiDoc file in your BASE_DIR
    with open(os.path.join(settings.BASE_DIR, input_file), "w") as f:
        f.write("== Test Document\n\nThis is a test.")

    # Run the management command
    management.call_command("convert_ascii", input_file)

    # Check that the output file exists
    assert os.path.exists(os.path.join(settings.BASE_DIR, output_file))

    # Check that the output contains a div with the id "content"
    with open(os.path.join(settings.BASE_DIR, output_file), "r") as f:
        assert 'id="content"' in f.read()
