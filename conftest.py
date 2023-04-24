import pytest
from django.contrib.auth import get_user_model
import tempfile
from PIL import Image
from test_plus import TestCase

from django.core.files import File as DjangoFile

User = get_user_model()

# Include the various pytest fixtures from all of our Django apps tests
# directories
pytest_plugins = [
    "libraries.tests.fixtures",
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


@pytest.fixture
def logged_in_tp(client):
    """
    TestPlus TestCase with a logged in user

    Use case: While the site is in development, this is a quick way to
    test views that require a logged in user.  This is a temporary
    solution that protects the new design from being seen by the public
    until it is ready.
    """
    email = "testuser@example.com"
    password = "testpassword"
    User.objects.create_user(email=email, password=password)
    client.login(email=email, password=password)

    tp = TestCase()
    tp.client = client

    return tp
