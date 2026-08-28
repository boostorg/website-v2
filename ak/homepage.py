"""Adapters turning backend data into V3 homepage template context."""

from django.urls import reverse

from badges.display import active_badges_prefetch
from core.constants import SLACK_MEMBER_COUNT
from core.models import HomepageSettings
from core.templatetags.custom_static import large_static
from libraries.models import FEATURED_LIBRARY_TIERS, Library, LibraryVersion
from libraries.utils import build_library_intro_context, get_documentation_url
from versions.models import Version
from pages.models import PostPage

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
        PostPage.objects.ranked()
        .select_related("owner", "owner__displayed_profile_role_library")
        # Badges per card, and the author's routing keys for the profile link.
        .prefetch_related(
            active_badges_prefetch("owner__badges"),
            "owner__profile_routing_keys",
        )
        .live()[:limit]
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

    Shows the libraries an editor curated in HomepageSettings; when fewer than
    `limit` are curated, the remaining slots are filled with random flagship/core
    libraries in the latest release (admins may curate more than `limit`). When
    admins curate libraries, their pinned order is preserved (fallback top-ups
    follow); with no pins, slides are ordered by description length for UI
    appearance. Returns a list of dicts (name, category_tags, description,
    added_in_version, docs_url); empty when no candidate library exists.
    """
    latest = Version.objects.most_recent()
    highlighted_ids = list(
        HomepageSettings.load().highlighted_libraries.values_list("id", flat=True)
    )
    library_ids = list(highlighted_ids)

    # Admins may curate more than `limit`; only top up when they curate fewer.
    remaining_slots = limit - len(highlighted_ids)
    if remaining_slots > 0:
        library_ids += list(
            Library.objects.filter(
                tier__in=FEATURED_LIBRARY_TIERS,
                library_version__version=latest,
            )
            .exclude(id__in=highlighted_ids)
            .distinct()
            .order_by("?")
            .values_list("id", flat=True)[:remaining_slots]
        )

    libraries = Library.objects.filter(id__in=library_ids).prefetch_related(
        "categories"
    )
    if not libraries:
        return []

    library_versions = {
        lv.library_id: lv
        for lv in LibraryVersion.objects.filter(library__in=libraries, version=latest)
    }

    category_list_url = reverse(
        "libraries-list",
        kwargs={"version_slug": "latest", "library_view_str": "list"},
    )

    slides_by_id = {}
    for library in libraries:
        lv = library_versions.get(library.id)
        first_version = library.first_boost_version
        # Fall back to the library detail page when the latest release has no
        # documentation URL, so the CTA always points somewhere useful.
        docs_url = get_documentation_url(lv, latest=True) if lv else ""
        if not docs_url:
            docs_url = reverse(
                "library-detail",
                kwargs={"version_slug": "latest", "library_slug": library.slug},
            )
        slides_by_id[library.id] = {
            "name": library.name,
            "category_tags": [
                (
                    {
                        **tag,
                        "url": f"{category_list_url}?category={tag['slug']}",
                        "aria_label": f"Browse {tag['label']} libraries",
                    }
                    if tag["slug"]
                    else tag
                )
                for tag in library.category_tags
            ],
            "description": (
                (lv.description if lv else None) or library.description or ""
            ),
            "added_in_version": (first_version.display_name if first_version else ""),
            "docs_url": docs_url,
        }

    if highlighted_ids:
        # Respect the admin's pinned order; fallback top-ups follow.
        return [slides_by_id[lib_id] for lib_id in library_ids]
    # No pins: order by description length, then category count, for looks.
    return sorted(
        slides_by_id.values(),
        key=lambda slide: (len(slide["description"]), len(slide["category_tags"])),
        reverse=True,
    )


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
