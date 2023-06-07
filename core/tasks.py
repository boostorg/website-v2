import os

import subprocess

from celery import shared_task


@shared_task
def adoc_to_html(file_path, delete_file=True):
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
