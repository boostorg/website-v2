import os

import subprocess

from celery import shared_task

from .asciidoc import adoc_to_html
from .boostrenderer import get_body_from_html, get_content_from_s3

from django.core.cache import caches

from .models import RenderedContent


@shared_task
def adoc_to_html(file_path, delete_file=True):
    return adoc_to_html(file_path, delete_file=delete_file)


@shared_task
def refresh_rendered_content_from_s3(content_path, cache_key):
    """ Take a cache """
    result = get_content_from_s3(key=content_path)
    if result and result.get("content"):
        content = result.get("content")
        content_type = result.get("content_type")
        last_updated_at_raw = result.get("last_updated_at")

        if content_type == "text/asciidoc":
            content = self.convert_adoc_to_html(content, cache_key)
            last_updated_at = (
                parse(last_updated_at_raw) if last_updated_at_raw else None
            )

    # Get the output from the command
    converted_html = result.stdout

    # Delete the temporary file
    if delete_file:
        os.remove(file_path)

    return converted_html
