import os
import subprocess

from django.conf import settings
from django.core.cache import caches
from celery import shared_task


@shared_task
def adoc_to_html(file_path, cache_key, content_type, delete_file=True):
    """
    Converts an AsciiDoc file to HTML and stores the result in the cache.
    If delete_file is True, the temporary file will be deleted after the
    conversion is complete.

    The asciidoctor package is a Ruby gem, which is why we're using subprocess
    to run the command.
    https://docs.asciidoctor.org/asciidoctor/latest/

    :param file_path: The path to the AsciiDoc file
    :param cache_key: The key to use when storing the result in the cache
    :param content_type: The content type of the file
    :param delete_file: Whether or not to delete the temporary file after the
    """
    result = subprocess.run(
        ["asciidoctor", "-o", "-", file_path],
        check=True,
        capture_output=True,
    )

    # Get the output from the command
    converted_html = result.stdout
    # Get the static content cache
    static_content_cache = caches["static_content"]

    # Store the HTML content in cache
    static_content_cache.set(
        cache_key,
        (converted_html, content_type),
        int(settings.CACHES["static_content"]["TIMEOUT"]),
    )

    # Delete the temporary file
    if delete_file:
        os.remove(file_path)

    return converted_html
