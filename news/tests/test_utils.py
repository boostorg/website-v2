from io import BytesIO
from sys import getsizeof
from PIL import Image

from django.core.files.uploadedfile import UploadedFile
from django.conf import settings

from news.utils import downsize_uploaded_image


def test_downscale_image():
    # Image that is far too large
    test_image = Image.effect_noise((1920 * 2, 1080 * 2), 100)
    b_io = BytesIO()
    test_image.save(b_io, format="png")
    test_upload = UploadedFile(b_io, "test_image.png")

    r_upload = downsize_uploaded_image(test_upload)

    assert getsizeof(test_upload.file) > settings.DOWNSCALE_THRESHOLD
    assert getsizeof(r_upload.file) < settings.DOWNSCALE_THRESHOLD
    assert r_upload.name == "test_image.webp"
