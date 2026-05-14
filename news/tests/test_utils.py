from io import BytesIO
from PIL import Image

from django.core.files.uploadedfile import UploadedFile
from django.conf import settings

from news.utils import downsize_uploaded_image


def test_downscale_image():
    # Image that is far too large
    test_image = Image.effect_noise((1920 * 2, 1080 * 2), 100)
    b_io = BytesIO()
    test_image.save(b_io, format="png")
    b_io.seek(0)
    test_upload = UploadedFile(b_io, "test_image.png")

    r_upload = downsize_uploaded_image(test_upload)

    assert test_upload.file.getbuffer().nbytes > settings.DOWNSCALE_IMAGE_THRESHOLD
    assert r_upload.file.getbuffer().nbytes < settings.DOWNSCALE_IMAGE_THRESHOLD
    assert r_upload.name == "test_image.webp"
