import math
import requests
import typing
from io import BytesIO
from PIL import Image as PImage

from django.conf import settings
from django.core.files import File
from django.core.files.uploadedfile import UploadedFile
from wagtail.images.models import Image

if typing.TYPE_CHECKING:
    from news.models import Video


def set_video_thumbnail(video: "Video"):
    """
    Given a video model, use oembed to fetch the thumbnail and save it to the model
    """
    YOUTUBE_OEMBED_ENDPOINT = "https://www.youtube.com/oembed"

    if not video.is_video:
        raise Exception(f"{video} is not a video, cannot set thumbnail.")

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
    video.thumbnail = image
    video.save()


def downsize_uploaded_image(image: UploadedFile) -> UploadedFile:
    """
    Takes a given image file from an upload form, and returns a downscaled image
    to take better use of available storage space.

    Does not handle the initial size comparison to determin if the image should be downsized.

    Downsizes the images using three methods:
        1) Downscales the image to specified parameters in the settings, maintaining the aspect ratio
        2) Converts the image to webp
        3) Uses Pillows built in compression algorithm to do available compression during saving

    Example Usage:

        def clean_image(self):
        image = self.cleaned_data.get("image", None)
        if image and image.size > settings.DOWNSCALE_THRESHOLD:
            return downsize_uploaded_image(image)
        return image
    """

    with PImage.open(image) as im:
        file_name = image.name
        if image_format := im.format:
            file_name = file_name.strip(image_format.lower())
            file_name += "webp"

        width, height = im.size
        p_width, p_height = None, None  # Preferred output image width and height
        s_width, s_height = (
            settings.DOWNSCALED_WIDTH,
            settings.DOWNSCALED_HEIGHT,
        )  # Settings based prefferred width and height

        # Scale the preferred width and height in a proportional manner, to not skew the image

        # Scale based on the dimension that is further off from preferred dimensions
        if width - s_width >= height - s_height:
            p_width = s_width
            p_height = math.floor((p_width / width) * height)
        else:
            p_height = s_height
            p_width = math.floor((p_height / height) * width)

        r_image = im.resize((p_width, p_height))

        # Save to a BytesIO, actual file system saving will be handled by the form calling this function
        imgstr = BytesIO()
        r_image.save(imgstr, format="webp")
        return UploadedFile(imgstr, name=file_name)
