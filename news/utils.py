import requests
import typing
from io import BytesIO

from django.core.files import File
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
