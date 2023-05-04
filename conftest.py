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
def tp(client):
    """
    django-test-plus TestCase with a logged in user.

    Use case: While the site is in development, this is a quick way to
    test views that require a logged in user.  This is a temporary
    solution that protects the new design from being seen by the public
    until it is ready.

    When you're done, remove this fixture. The tests will automatically update
    to use the standard django-test-plus test class.
    """
    email = "testuser@example.com"
    password = "testpassword"
    User.objects.create_user(email=email, password=password)
    client.login(email=email, password=password)

    tp = TestCase()
    tp.client = client

    return tp


@pytest.fixture
def logged_out_tp(client):
    """
    django-test-plus TestCase with a logged-out user.

    Use case: While the `tp` fixture is being overriden to allow tests
    to pass while the whole site is behind login, this fixture allows
    tests to be written for the public-facing pages.

    When you're done, remove this fixture and update tests that use it to
    use the standard django-test-plus client fixture.
    """
    email = "testuser@example.com"
    password = "testpassword"
    User.objects.create_user(email=email, password=password)
    client.login(email=email, password=password)

    tp = TestCase()
    tp.client = client

    return tp
