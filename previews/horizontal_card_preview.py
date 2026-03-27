from django_lookbook.preview import LookbookPreview
from django.template.loader import render_to_string
from django.conf import settings


class HorizontalCardPreview(LookbookPreview):

    def default(self, **kwargs):
        """
        Horizontal card with side-by-side text and image, plus CTA button.

        Template: `v3/includes/_horizontal_card.html`

        | Variable | Required | Description |
        |---|---|---|
        | `title` | Yes | Card heading |
        | `text` | Yes | Description text beside the image |
        | `image_url` | Yes | URL of the image |
        | `image_alt` | No | Alt text for image |
        | `button_url` | No | CTA link destination |
        | `button_label` | No | CTA button text |
        | `button_style` | No | Button style variant |
        """
        return render_to_string(
            "v3/includes/_horizontal_card.html",
            {
                "title": "Build anything with Boost",
                "text": "Use, modify, and distribute Boost libraries freely. No binary attribution needed.",
                "image_url": f"{settings.STATIC_URL}img/checker.png",
                "button_url": "#",
                "button_label": "See license details",
            },
        )
