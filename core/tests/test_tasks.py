import pytest
import tempfile
from unittest.mock import patch

from django.core.cache import caches
from django.test import override_settings

from core.tasks import adoc_to_html


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "unique-snowflake",
        },
        "machina_attachments": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "another-unique-snowflake",
        },
        "static_content": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "third-unique-snowflake",
            "TIMEOUT": "60",  # Cache timeout in seconds: 1 minute
        },
    }
)
def test_adoc_to_html():
    # Get the static content cache
    caches["static_content"]

    # The content of the sample adoc file
    sample_adoc_content = "= Document Title\n\nThis is a sample document.\n"

    # Write the content to a temporary file
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(sample_adoc_content.encode())
        temp_file_path = temp_file.name

    # Execute the task
    with patch("core.tasks.subprocess.run") as mock_run:
        mock_run.return_value.stdout = "html_content".encode()
        adoc_to_html(temp_file_path, delete_file=True)

    # Verify that the temporary file has been deleted
    with pytest.raises(FileNotFoundError):
        with open(temp_file_path, "r"):
            pass
