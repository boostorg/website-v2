import pytest
import tempfile
from PIL import Image

from django.core.files import File as DjangoFile

# Include the various pytest fixtures from all of our Django apps tests
# directories
pytest_plugins = [
    "core.tests.fixtures",
    "libraries.tests.fixtures",
    "news.tests.fixtures",
    "users.tests.fixtures",
    "versions.tests.fixtures",
]


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
