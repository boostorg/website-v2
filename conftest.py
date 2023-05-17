import pytest
import tempfile
from PIL import Image

from django.core.files import File as DjangoFile

# Include the various pytest fixtures from all of our Django apps tests
# directories
pytest_plugins = [
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
