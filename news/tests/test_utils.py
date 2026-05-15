from io import BytesIO
from PIL import Image

from django.core.files.uploadedfile import UploadedFile
from django.conf import settings

from news.utils import downsize_uploaded_image


def test_downscale_image():
    """
    Rigorous test of basic usage of the dowscale functionality:

        * Basic sanity test that we produce an image large enough to be downscaled
        * Test that the downscaled image is smaller than our threshold
        * Test that the image was renamed properly
        * Test that the aspect ratio has not mutated when downscaling (portrait remains portrait as well)
        * Test that we actually hit our preferred width/height values when downscaling
    """
    # Image that is far too large
    initial_width = 1920 * 2
    initial_height = 1080 * 2
    initial_aspect = initial_width / initial_height
    test_image = Image.effect_noise((initial_width, initial_height), 100)
    img = BytesIO()
    test_image.save(img, format="png")
    img.seek(0)
    test_upload = UploadedFile(img, "test_image.png")

    r_upload = downsize_uploaded_image(test_upload)

    # Tests to assert basic functionality of the downscale
    assert test_upload.file.getbuffer().nbytes > settings.DOWNSCALE_IMAGE_THRESHOLD
    assert r_upload.file.getbuffer().nbytes < settings.DOWNSCALE_IMAGE_THRESHOLD
    assert r_upload.name == "test_image.webp"

    # Tests to assert our output hasn't mutated
    downscale_image = Image.open(r_upload.file)
    width, height = downscale_image.size
    assert width / height == initial_aspect

    # Assert that we actually are smaller than specified settings
    assert width <= settings.DOWNSCALED_IMAGE_WIDTH
    assert height <= settings.DOWNSCALED_IMAGE_HEIGHT


def test_upscaled_edgecase():
    """
    Test that if an image smaller than our preferred width/height somehow makes it in,
    it doesn't somehow end up upscaled
    """
    # Image that is smaller than our minimum size
    initial_width = settings.DOWNSCALED_IMAGE_WIDTH - 1
    initial_height = settings.DOWNSCALED_IMAGE_HEIGHT - 1
    test_image = Image.effect_noise((initial_width, initial_height), 1)
    img = BytesIO()
    test_image.save(img, format="png")
    img.seek(0)
    test_upload = UploadedFile(img, "test_image.png")

    r_upload = downsize_uploaded_image(test_upload)

    # Image should not have changed, other than being turned into a webp
    downscale_image = Image.open(r_upload.file)
    width, height = downscale_image.size
    assert r_upload.name == "test_image.webp"
    assert width == initial_width
    assert height == initial_height


def test_name_edgecase():
    """
    Test that if we try to downscale an image with a name containing an extension (e.g. png_test.png)
    that it properly strips the extension, but doesn't mutate the file name
    """
    initial_width = 1920
    initial_height = 1080
    test_image = Image.effect_noise((initial_width, initial_height), 1)
    img = BytesIO()
    test_image.save(img, format="png")
    img.seek(0)
    test_upload = UploadedFile(img, "png_test.png")

    r_upload = downsize_uploaded_image(test_upload)
    assert r_upload.name == "png_test.webp"
