"""Per-surface hero image context.

Centralizes the hero image URLs each v3 surface feeds into the tokenized
`_hero_home.html` / `_hero_library.html` components, so views call one helper
instead of hardcoding `large_static(...)` paths inline. Combines the centralized
helper pattern from the Homepage Integration work (#2480) with the tokenized
hero component from the hero refactor (#2432).
"""

from core.templatetags.custom_static import large_static


def home_hero_context():
    """Hero image context for the home page."""
    foreground = large_static("img/v3/home-page/home-page-foreground.png")
    return {
        "hero_image_url": foreground,
        "hero_image_url_light": foreground,
        "hero_image_url_dark": foreground,
        # Mobile art-direction: a tightly-trimmed foreground so it isn't
        # letterboxed on narrow screens. Desktop/tablet keep the wide foreground.
        "hero_image_url_mobile": large_static(
            "img/v3/home-page/home-page-foreground-mobile.png"
        ),
        "hero_background_image_url": large_static(
            "img/v3/home-page/home-page-background.png"
        ),
    }


def community_hero_context():
    """Hero image context for the community page."""
    return {
        "hero_image_url": large_static(
            "img/v3/community-page/community-foreground.png"
        ),
        # Mobile art-direction: a tighter crop swapped in via <picture> at <=767px.
        "hero_image_url_mobile": large_static(
            "img/v3/community-page/community-foreground-mobile.png"
        ),
        "hero_background_image_url": large_static(
            "img/v3/community-page/community-background.png"
        ),
    }


def release_hero_context():
    """Hero image context for the release detail page (the downloads hero)."""
    return {
        "hero_image_url": large_static("img/v3/releases-page/release-foreground.png"),
        # Mobile art-direction: the illustration is redrawn as a portrait scene
        # for narrow screens rather than cropped, so it carries its own sky and
        # needs the taller ratio set in heros.css (--hero-fg-aspect).
        "hero_image_url_mobile": large_static(
            "img/v3/releases-page/release-foreground-mobile.png"
        ),
        "hero_background_image_url": large_static(
            "img/v3/releases-page/release-background.png"
        ),
    }
