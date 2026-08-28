"""Tests for the V3 WYSIWYG editor's image-upload endpoint."""

import io

import pytest
import waffle.testutils
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from core.models import UPLOADED_IMAGE_DIRECTORY, WysiwygImage

pytestmark = pytest.mark.django_db


def _png(size=(20, 20), name="diagram.png"):
    """An in-memory PNG upload of the given pixel size."""
    buffer = io.BytesIO()
    Image.new("RGB", size).save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


@pytest.fixture
def cleanup_uploads():
    """Delete whatever the tests wrote to storage, so runs don't accumulate files."""
    written = []
    yield written
    for name in written:
        default_storage.delete(name)


def _stored_name(url):
    """The storage name behind a returned media URL (i.e. minus MEDIA_URL)."""
    return url[url.index(f"{UPLOADED_IMAGE_DIRECTORY}/") :]


@waffle.testutils.override_flag("v3", active=True)
def test_upload_stores_the_image_and_returns_its_url(user, tp, cleanup_uploads):
    with tp.login(user):
        response = tp.post(
            tp.reverse("v3-wysiwyg-image-upload"), data={"image": _png()}
        )

    assert response.status_code == 200
    url = response.json()["url"]
    assert f"{UPLOADED_IMAGE_DIRECTORY}/" in url
    stored = _stored_name(url)
    cleanup_uploads.append(stored)
    assert default_storage.exists(stored)
    # The client's filename is attacker-controlled and never reaches the path.
    assert "diagram" not in url

    upload = WysiwygImage.objects.get()
    assert upload.image.name == stored
    assert upload.uploaded_by == user
    assert upload.original_filename == "diagram.png"
    assert (upload.width, upload.height) == (20, 20)


@waffle.testutils.override_flag("v3", active=True)
def test_deleting_the_row_removes_the_file(
    user, tp, cleanup_uploads, django_capture_on_commit_callbacks
):
    """Deleting an upload in the admin is what takes it out of storage."""
    with tp.login(user):
        response = tp.post(
            tp.reverse("v3-wysiwyg-image-upload"), data={"image": _png()}
        )
    stored = _stored_name(response.json()["url"])
    cleanup_uploads.append(stored)

    with django_capture_on_commit_callbacks(execute=True):
        # Through the queryset, as the admin's bulk action deletes.
        WysiwygImage.objects.all().delete()

    assert not default_storage.exists(stored)


@waffle.testutils.override_flag("v3", active=True)
def test_upload_requires_login(tp):
    response = tp.post(tp.reverse("v3-wysiwyg-image-upload"), data={"image": _png()})

    tp.response_302(response)
    assert "login" in response.url


@waffle.testutils.override_flag("v3", active=False)
def test_upload_404s_when_the_v3_flag_is_off(user, tp):
    with tp.login(user):
        response = tp.post(
            tp.reverse("v3-wysiwyg-image-upload"), data={"image": _png()}
        )

    tp.response_404(response)


@waffle.testutils.override_flag("v3", active=True)
def test_upload_rejects_a_non_image(user, tp):
    upload = SimpleUploadedFile("notes.txt", b"not an image", content_type="text/plain")
    with tp.login(user):
        response = tp.post(
            tp.reverse("v3-wysiwyg-image-upload"), data={"image": upload}
        )

    assert response.status_code == 400
    assert response.json()["error"]


@waffle.testutils.override_flag("v3", active=True)
def test_upload_rejects_a_disallowed_image_extension(user, tp):
    """A real image is still refused unless its extension is jpg/jpeg/png."""
    buffer = io.BytesIO()
    Image.new("RGB", (20, 20)).save(buffer, format="GIF")
    upload = SimpleUploadedFile("anim.gif", buffer.getvalue(), content_type="image/gif")
    with tp.login(user):
        response = tp.post(
            tp.reverse("v3-wysiwyg-image-upload"), data={"image": upload}
        )

    assert response.status_code == 400
    assert "Unsupported file extension" in response.json()["error"]


@waffle.testutils.override_flag("v3", active=True)
def test_upload_rejects_a_get(user, tp):
    with tp.login(user):
        response = tp.get(tp.reverse("v3-wysiwyg-image-upload"))

    assert response.status_code == 405


@waffle.testutils.override_flag("v3", active=True)
def test_large_upload_is_downscaled_to_webp(user, tp, settings, cleanup_uploads):
    """Oversized images are re-encoded, as the V3 post forms already do."""
    settings.DOWNSCALE_IMAGE_THRESHOLD = 1
    with tp.login(user):
        response = tp.post(
            tp.reverse("v3-wysiwyg-image-upload"),
            data={"image": _png(size=(2000, 200))},
        )

    assert response.status_code == 200
    url = response.json()["url"]
    assert url.endswith(".webp")
    cleanup_uploads.append(_stored_name(url))
