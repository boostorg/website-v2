"""Per-surface hero image context.

Centralizes the hero image URLs each v3 surface feeds into the tokenized
`_hero_home.html` / `_hero_library.html` components, so views call one helper
instead of hardcoding `large_static(...)` paths inline. Combines the centralized
helper pattern from the Homepage Integration work (#2480) with the tokenized
hero component from the hero refactor (#2432).
"""

from core.templatetags.custom_static import large_static


def home_hero_context():
    """Hero image context for the home page.

    The home and community heroes are swapped by design (see
    `community_hero_context`): the home page renders the community scene.
    """
    foreground = large_static("img/v3/community-page/community-foreground.png")
    return {
        "hero_image_url": foreground,
        "hero_image_url_light": foreground,
        "hero_image_url_dark": foreground,
        # Mobile art-direction: a tightly-trimmed foreground so it isn't
        # letterboxed on narrow screens. Desktop/tablet keep the wide foreground.
        "hero_image_url_mobile": large_static(
            "img/v3/community-page/community-foreground-mobile.png"
        ),
        "hero_background_image_url": large_static(
            "img/v3/home-page/home-hero-background.png"
        ),
    }


def community_hero_context():
    """Hero image context for the community page (renders the home scene; see swap)."""
    return {
        "hero_image_url": large_static("img/v3/home-page/home-page-foreground.png"),
        # Mobile art-direction: a tighter crop swapped in via <picture> at <=767px.
        "hero_image_url_mobile": large_static(
            "img/v3/home-page/home-page-foreground-mobile.png"
        ),
        "hero_background_image_url": large_static(
            "img/v3/home-page/home-page-background.png"
        ),
    }


def release_hero_context():
    """Hero image context for the release detail page."""
    return {
        "hero_image_url": large_static("img/v3/releases-page/release-foreground.png"),
        "hero_image_url_mobile": large_static(
            "img/v3/releases-page/release-foreground-mobile.png"
        ),
        "hero_background_image_url": large_static(
            "img/v3/releases-page/release-background.png"
        ),
    }
