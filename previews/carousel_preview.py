from django_lookbook.preview import LookbookPreview
from django.template.loader import render_to_string


SAMPLE_CARDS = [
    {
        "title": "Get help",
        "description": "Tap into quick answers, networking, and chat with 24,000+ members.",
        "icon_name": "info-box",
        "cta_label": "Start here",
        "cta_href": "#",
    },
    {
        "title": "Documentation",
        "description": "Browse library docs, examples, and release notes in one place.",
        "icon_name": "link",
        "cta_label": "View docs",
        "cta_href": "#",
    },
    {
        "title": "Community",
        "description": "Mailing lists, GitHub, and community guidelines for contributors.",
        "icon_name": "human",
        "cta_label": "Join",
        "cta_href": "#",
    },
    {
        "title": "Releases",
        "description": "Latest releases, download links, and release notes.",
        "icon_name": "info-box",
        "cta_label": "Download",
        "cta_href": "#",
    },
    {
        "title": "Libraries",
        "description": "Explore the full catalog of Boost C++ libraries with docs and metadata.",
        "icon_name": "link",
        "cta_label": "Browse libraries",
        "cta_href": "#",
    },
    {
        "title": "News",
        "description": "Blog posts, announcements, and community news from the Boost project.",
        "icon_name": "device-tv",
        "cta_label": "Read news",
        "cta_href": "#",
    },
    {
        "title": "Getting started",
        "description": "Step-by-step guides to build and use Boost in your projects.",
        "icon_name": "bullseye-arrow",
        "cta_label": "Get started",
        "cta_href": "#",
    },
    {
        "title": "Resources",
        "description": "Learning resources, books, and other materials for Boost users.",
        "icon_name": "get-help",
        "cta_label": "View resources",
        "cta_href": "#",
    },
]


class CarouselButtonsPreview(LookbookPreview):

    def default(self, **kwargs):
        """
        Standalone carousel navigation buttons (previous / next).

        Template: `v3/includes/_carousel_buttons.html`

        | Variable | Required | Description |
        |---|---|---|
        | `carousel_id` | No | ID prefix for JS hooks |
        | `prev_label` | No | Aria-label for previous button. Default: "Previous" |
        | `next_label` | No | Aria-label for next button. Default: "Next" |
        """
        return render_to_string("v3/includes/_carousel_buttons.html")


class CardsCarouselPreview(LookbookPreview):

    def default(self, **kwargs):
        """
        Detail card carousel — horizontal scrolling cards with heading and navigation.

        Template: `v3/includes/_cards_carousel_v3.html`

        | Variable | Required | Description |
        |---|---|---|
        | `carousel_id` | Yes | Unique id for the carousel |
        | `heading` | Yes | Section heading |
        | `cards` | No | List of dicts with: title, description, icon_name, cta_label, cta_href |
        | `track_aria_label` | No | Aria-label for the track. Default: "Detail cards carousel" |
        | `infinite` | No | If True, carousel loops. Default: False |
        | `autoplay` | No | If True, auto-scrolls. Default: False |
        | `autoplay_delay` | No | Autoplay interval in ms. Default: 4000 |
        """
        return render_to_string(
            "v3/includes/_cards_carousel_v3.html",
            {
                "carousel_id": "lookbook-carousel-default",
                "heading": "Libraries categories",
                "cards": SAMPLE_CARDS,
            },
        )

    def with_autoplay(self, **kwargs):
        """
        Cards carousel with autoplay enabled (5-second interval).
        """
        return render_to_string(
            "v3/includes/_cards_carousel_v3.html",
            {
                "carousel_id": "lookbook-carousel-autoplay",
                "heading": "Libraries categories",
                "cards": SAMPLE_CARDS,
                "autoplay": True,
                "autoplay_delay": 5000,
            },
        )

    def with_infinite_and_autoplay(self, **kwargs):
        """
        Cards carousel with infinite looping and autoplay enabled.
        """
        return render_to_string(
            "v3/includes/_cards_carousel_v3.html",
            {
                "carousel_id": "lookbook-carousel-infinite",
                "heading": "Libraries categories",
                "cards": SAMPLE_CARDS,
                "infinite": True,
                "autoplay": True,
                "autoplay_delay": 5000,
            },
        )
