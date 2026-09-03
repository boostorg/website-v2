import os

import pytest
import tempfile
from PIL import Image

from django.core.files import File as DjangoFile
from django.db import connection

# Include the various pytest fixtures from all of our Django apps tests
# directories
pytest_plugins = [
    "badges.tests.fixtures",
    "core.tests.fixtures",
    "libraries.tests.fixtures",
    "news.tests.fixtures",
    "pages.tests.fixtures",
    "users.tests.fixtures",
    "versions.tests.fixtures",
]


# --no-migrations keeps core/migrations 0011 and 0012 off the test database.
# Idempotent, because --reuse-db means this re-runs against an existing one.
SEARCH_CONFIG_SQL = """
CREATE EXTENSION IF NOT EXISTS unaccent;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_ts_config WHERE cfgname = 'english_unaccent')
    THEN
        CREATE TEXT SEARCH CONFIGURATION english_unaccent ( COPY = english );
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_ts_config WHERE cfgname = 'simple_unaccent')
    THEN
        CREATE TEXT SEARCH CONFIGURATION simple_unaccent ( COPY = simple );
    END IF;
END $$;
ALTER TEXT SEARCH CONFIGURATION english_unaccent
  ALTER MAPPING FOR hword, hword_part, word WITH unaccent, english_stem;
ALTER TEXT SEARCH CONFIGURATION simple_unaccent
  ALTER MAPPING FOR hword, hword_part, word WITH unaccent, simple;
"""


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        with connection.cursor() as cursor:
            cursor.execute(SEARCH_CONFIG_SQL)


@pytest.fixture
def temp_image_file():
    image = Image.new("RGB", (100, 100))

    tmp_file = tempfile.NamedTemporaryFile(suffix=".jpg")
    image.save(tmp_file)

    tmp_file.seek(0)
    file_obj = DjangoFile(open(tmp_file.name, mode="rb"), name="tmp_file")
    yield file_obj.seek(0)


def pytest_collection_modifyitems(config, items):
    """
    Adds support for skipping tests based on the presence of markers:
     - asciidoctor
    """
    keywordexpr = config.option.keyword
    markexpr = config.option.markexpr
    if keywordexpr or markexpr:
        return  # let pytest handle this

    skip_asciidoctor = pytest.mark.skip(reason="asciidoctor not selected")
    for item in items:
        if "asciidoctor" in item.keywords:
            item.add_marker(skip_asciidoctor)


@pytest.fixture(scope="session", autouse=True)
def ensure_github_token_env_variable():
    # I wanted to use pytest_env but skip_if_set=true only applies if the env var
    # is not set at all, not if the env var is empty, so this is needed anyway.
    VAR_NAME = "GITHUB_TOKEN"  # Replace with your actual variable name
    VAR_DEFAULT_VALUE = "top-secret"
    current_value = os.getenv(VAR_NAME)

    if not current_value:
        os.environ[VAR_NAME] = VAR_DEFAULT_VALUE
        print(f"Env variable '{VAR_NAME}' not set. Forced to {VAR_DEFAULT_VALUE=}.")


@pytest.fixture(scope="session")
def celery_config():
    return {"broker_url": "amqp://", "result_backend": "redis://"}
