from django_lookbook.preview import LookbookPreview
from django.template.loader import render_to_string


class BannerPreview(LookbookPreview):

    def default(self, **kwargs):
        """
        Alert banner with icon and message.

        Template: `v3/includes/_banner.html`

        | Variable | Required | Description |
        |---|---|---|
        | `banner_message` | Yes | HTML content for the banner message |
        | `icon_name` | No | Icon name (see `includes/icon.html`) |
        | `fade_time` | No | Time in ms after which the banner fades out |
        """
        return render_to_string(
            "v3/includes/_banner.html",
            {
                "icon_name": "alert",
                "banner_message": "This is an older version of Boost and was released in 2017. The <a href='https://www.example.com'>current version</a> is 1.90.0.",
            },
        )

    def with_fade(self, **kwargs):
        """
        Alert banner with auto-fade after 5 seconds.
        """
        return render_to_string(
            "v3/includes/_banner.html",
            {
                "icon_name": "alert",
                "banner_message": "This is an older version of Boost and was released in 2017. The <a href='https://www.example.com'>current version</a> is 1.90.0.",
                "fade_time": 5000,
            },
        )
