"""Adapters turning backend data into V3 homepage template context."""

from django.urls import reverse

from core.constants import SLACK_MEMBER_COUNT
from core.models import HomepageSettings
from core.templatetags.custom_static import large_static
from libraries.models import FEATURED_LIBRARY_TIERS, Library, LibraryVersion
from libraries.utils import build_library_intro_context, get_documentation_url
from news.models import Entry
from versions.models import Version

# Hero illustration for the V3 homepage.
HERO_LEGACY_IMAGE_URL_LIGHT = large_static("img/v3/home-page/heros.png")
HERO_LEGACY_IMAGE_URL_DARK = large_static("img/v3/home-page/heros_light.png")
HERO_FOREGROUND_IMAGE_URL = large_static("img/v3/home-page/home-page-foreground.png")


def get_v3_featured_library():
    """LibraryVersion to feature on the V3 homepage.

    Prefers the library an editor chose in HomepageSettings, otherwise a
    random flagship- or core-tier library. Falls back to a random library
    when the configured one has no LibraryVersion for the latest release
    Returns None only when no candidate library has a latest-release row.
    """
    library = HomepageSettings.load().featured_library
    latest_version = Version.objects.most_recent()

    if library:
        library_version = LibraryVersion.objects.filter(
            library=library, version=latest_version
        ).first()
        if library_version:
            return library_version

    return (
        LibraryVersion.objects.filter(
            version=latest_version,
            library__tier__in=FEATURED_LIBRARY_TIERS,
        )
        .order_by("?")
        .first()
    )


# Static "Why Boost" card grid; pure presentation data so it lives at module
# scope rather than being rebuilt per request.
WHY_BOOST_CARDS = [
    {
        "title": "Performant",
        "description": "Optimized for production at any scale, Boost outperforms many standard benchmarks.",
        "icon_name": "speed-fast",
        "icon_viewbox": "0 0 16 16",
    },
    {
        "title": "Peer-reviewed",
        "description": "Well tested by members of the C++ standards committee.",
        "icon_name": "eye",
    },
    {
        "title": "Portable",
        "description": "Works across all platforms, compilers, and C++ standards.",
        "icon_name": "arrows-horizontal",
        "icon_viewbox": "0 0 16 16",
    },
    {
        "title": "Free",
        "description": "Open source now and always, thanks to the Boost Software License.",
        "icon_name": "lock",
        "icon_viewbox": "0 0 16 16",
    },
    {
        "title": "Innovative",
        "description": "Over 40 Boost libraries have become part of the C++ standard over the past 25 years.",
        "icon_name": "bookmarks",
        "icon_viewbox": "0 0 16 16",
    },
    {
        "title": "Community-powered",
        "description": "Contributing to Boost builds credibility, sharpens skills, and advances careers.",
        "icon_name": "users",
        "icon_viewbox": "0 0 16 16",
    },
    {
        "title": "Known worldwide",
        "description": "Used in countless projects, you've probably encountered Boost without realizing it",
        "icon_name": "building-community",
        "icon_viewbox": "0 0 16 16",
    },
    {
        "title": "Production-ready",
        "description": "Battle-tested in critical systems across industries around the globe.",
        "icon_name": "zap",
        "icon_viewbox": "0 0 16 16",
    },
]


def build_community_posts(limit=5):
    """Top-ranked posts shown on the V3 homepage.

    Returns just the list of post dicts; the surrounding card chrome
    (heading, CTA, variant, theme) lives in the template. Uses
    `Entry.ranked()` (popularity-ordered), not chronological.
    """
    popular_entries = (
        Entry.objects.ranked()
        .filter(deleted_at__isnull=True, published=True)
        .select_related("author")[:limit]
    )
    return [entry.to_v3_post_card_dict() for entry in popular_entries]


def build_join_developers_links():
    """Three-link list for the 'Join developers building the future of C++'
    card. Surrounding card chrome (heading, CTA, variant, theme) lives in
    the template.
    """
    return [
        {
            "title": "Get help",
            "description": f"Tap into quick answers, networking, and chat with {SLACK_MEMBER_COUNT} members.",
            "icon_name": "message",
            "icon_viewbox": "0 0 16 16",
            "url": "https://cppalliance.org/slack/",
        },
        {
            "title": "Contribute",
            "description": "Learn how to test or evaluate library submissions, or submit your own.",
            "icon_name": "documentation",
            "icon_viewbox": "0 0 16 16",
            "url": reverse(
                "docs-user-guide",
                kwargs={"content_path": "contributor-guide/contributors-faq.html"},
            ),
        },
        {
            "title": "Stay updated",
            "description": "Get updates on the latest releases, fixes and announcements.",
            "icon_name": "bullseye-pixel",
            "url": "https://lists.boost.org/mailman3/lists/boost-announce.lists.boost.org/",
        },
    ]


def build_library_highlight_carousel(limit=3):
    """Per-slide content for the homepage 'Explore battle tested libraries'
    carousel.

    Shows the libraries an editor curated in HomepageSettings first (in random
    order); when fewer than `limit` are curated, the remaining slots are filled
    with random flagship/core libraries in the latest release. Returns a list
    of dicts (name, category_tags, description, added_in_version, docs_url);
    empty when no candidate library exists.
    """
    latest = Version.objects.most_recent()
    libraries = list(
        HomepageSettings.load()
        .highlighted_libraries.prefetch_related("categories")
        .order_by("?")
    )

    remaining_slots = limit - len(libraries)
    if remaining_slots > 0:
        libraries += list(
            Library.objects.filter(
                tier__in=FEATURED_LIBRARY_TIERS,
                library_version__version=latest,
            )
            .exclude(id__in=[lib.id for lib in libraries])
            .distinct()
            .prefetch_related("categories")
            .order_by("?")[:remaining_slots]
        )
    if not libraries:
        return []

    library_versions = {
        lv.library_id: lv
        for lv in LibraryVersion.objects.filter(library__in=libraries, version=latest)
    }

    slides = []
    for library in libraries:
        lv = library_versions.get(library.id)
        first_version = library.first_boost_version
        slides.append(
            {
                "name": library.display_name_short,
                "category_tags": library.category_tags,
                "description": (
                    (lv.description if lv else None) or library.description or ""
                ),
                "added_in_version": (
                    first_version.display_name if first_version else ""
                ),
                "docs_url": get_documentation_url(lv, latest=True) if lv else "",
            }
        )
    slides.sort(
        key=lambda slide: (len(slide["description"]), len(slide["category_tags"])),
        reverse=True,
    )  # sort by description length, then category count, to improve UI appearance
    return slides


def build_library_intro():
    """Library Intro card content for the V3 homepage, or None if no
    featured library is available.
    """
    featured_library = get_v3_featured_library()
    if not featured_library:
        return None
    return build_library_intro_context(featured_library, include_contributors=False)


def hero_image_context():
    """Hero image URLs used by `_hero_home.html`"""
    return {
        "hero_legacy_image_url_light": HERO_LEGACY_IMAGE_URL_LIGHT,
        "hero_legacy_image_url_dark": HERO_LEGACY_IMAGE_URL_DARK,
        "hero_image_url": HERO_FOREGROUND_IMAGE_URL,
        "hero_image_url_light": HERO_FOREGROUND_IMAGE_URL,
        "hero_image_url_dark": HERO_FOREGROUND_IMAGE_URL,
    }
