import os
import subprocess

from django.conf import settings
from django.core.cache import caches
from celery import shared_task


@shared_task
def adoc_to_html(file_path, cache_key):
    subprocess.run(
        ["asciidoctor", "-o", "-", "-"],
        input=file_path,
        text=True,
        check=True,
        capture_output=True,
    )

    # Get the static content cache
    static_content_cache = caches["static_content"]

    # Store the HTML content in cache
    static_content_cache.set(
        cache_key,
        ("html_content", "text/html"),
        int(settings.CACHES["static_content"]["TIMEOUT"]),
    )

    # Delete the temporary file
    os.remove(file_path)
