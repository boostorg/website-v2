import os
import requests
import typing
from io import BytesIO
from PIL import Image as PImage
from PIL import ImageOps

from django.conf import settings
from django.core.files import File
from django.core.files.uploadedfile import UploadedFile
from wagtail.images.models import Image

if typing.TYPE_CHECKING:
    from news.models import Video
    from pages.models import PostPage


def set_video_thumbnail(video: typing.Union["Video", "PostPage"]):
    """
    Given a video model, use oembed to fetch the thumbnail and save it to the model
    """
    from news.models import Video
    from pages.models import PostPage

    YOUTUBE_OEMBED_ENDPOINT = "https://www.youtube.com/oembed"

    if isinstance(video, Video) and not video.is_video:
        raise Exception(f"{video} is not a video, cannot set thumbnail.")
    elif isinstance(video, PostPage) and not video.post_content_type == "Video":
        raise Exception(f"{video}'s content is not a video, cannot set thumbnail.")

    url = YOUTUBE_OEMBED_ENDPOINT + f"?url={video.external_url}"
    response = requests.get(url)

    if not response.ok:
        raise Exception(f"Oembed API Error: {response.text}")

    json = response.json()
    thumbnail_file = File(
        BytesIO(requests.get(json.get("thumbnail_url")).content),
        name={f"{video.slug} Thumbnail"},
    )
    image = Image.objects.create(
        title=f"{video.slug} Thumbnail",
        file=thumbnail_file,
        width=json.get("thumbnail_width"),
        height=json.get("thumbnail_height"),
    )

    if isinstance(video, Video):
        video.thumbnail = image
    elif isinstance(video, PostPage):
        video.video_thumbnail = image
    video.save()


def downsize_uploaded_image(image: UploadedFile) -> UploadedFile:
    """
    Takes a given image file from an upload form, and returns a downscaled image
    to take better use of available storage space.

    Does not handle the initial size comparison to determine if the image should be downsized.

    Downsizes the images using three methods:
        1) Downscales the image to specified parameters in the settings, maintaining the aspect ratio
        2) Converts the image to webp
        3) Uses Pillow's built in compression algorithm to do available compression during saving

    Example Usage:

        def clean_image(self):
            image = self.cleaned_data.get("image", None)
            if image and image.size > settings.DOWNSCALE_IMAGE_THRESHOLD:
                return downsize_uploaded_image(image)
            return image
    """

    with PImage.open(image) as im:
        file_name = image.name
        root, ext = os.path.splitext(file_name)
        if root:
            file_name = root
            file_name += ".webp"

        s_width, s_height = (
            settings.DOWNSCALED_IMAGE_WIDTH,
            settings.DOWNSCALED_IMAGE_HEIGHT,
        )  # Settings based preferred width and height

        # Bake EXIF orientation into pixels so portrait phone photos don't end up sideways
        im = ImageOps.exif_transpose(im)

        # Use the thumbnail functionality to reduce this image to our preferred width and height.
        # Maintains aspect ratio, and won't ever upscale.
        im.thumbnail((s_width, s_height), PImage.Resampling.LANCZOS)

        # Save to a BytesIO, actual file system saving will be handled by the form calling this function
        img = BytesIO()
        im.save(img, format="webp")
        img.seek(0)
        return UploadedFile(
            img,
            name=file_name,
            content_type="image/webp",
            size=img.getbuffer().nbytes,
        )
