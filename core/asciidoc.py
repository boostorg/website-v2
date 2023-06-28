import os
import subprocess
import tempfile

from .boostrenderer import get_body_from_html


def convert_adoc_to_html(file_path, delete_file= True):
    """
    Converts an AsciiDoc file to HTML.
    If delete_file is True, the temporary file will be deleted after the
    conversion is complete.

    Note: This returns the full <html> document, including the <head> and
    <body> tags.

    The asciidoctor package is a Ruby gem, which is why we're using subprocess
    to run the command.
    https://docs.asciidoctor.org/asciidoctor/latest/

    :param file_path: The path to the AsciiDoc file
    :param delete_file: Whether or not to delete the temporary file after the
        conversion is complete
    """
    result = subprocess.run(
        ["asciidoctor", "-o", "-", file_path],
        check=True,
        capture_output=True,
    )

    # Get the output from the command
    converted_html = result.stdout

    # Delete the temporary file
    if delete_file:
        os.remove(file_path)

    return converted_html


def process_adoc_to_html_content(content):
    """Renders asciidoc content to HTML."""
    # Write the content to a temporary file
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        if isinstance(content, str):
            content = content.encode()
        temp_file.write(content)

    html_content = convert_adoc_to_html(temp_file.name, delete_file=True)
    if isinstance(html_content, bytes):
        html_content = html_content.decode("utf-8")

    # Extract only the contents of the body tag that we want from the HTML
    return get_body_from_html(html_content)
