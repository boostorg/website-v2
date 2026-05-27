"""Adapters turning backend data into V3 homepage template context."""

from core.models import HomepageSettings
from libraries.models import Library, LibraryVersion, Tier
from news.models import Entry
from versions.models import Version


def get_v3_featured_library():
    """LibraryVersion to feature on the V3 homepage.

    Prefers the library an editor chose in HomepageSettings, otherwise a
    random flagship-tier library. Resolves to that library's latest-release LibraryVersion, or None if it has none.
    """
    library = HomepageSettings.load().featured_library
    latest_version = Version.objects.most_recent()

    if not library:
        library = (
            Library.objects.filter(
                tier=Tier.FLAGSHIP, library_version__version=latest_version
            )
            .order_by("?")
            .first()
        )
    if not library:
        return None

    return LibraryVersion.objects.filter(
        library=library, version=latest_version
    ).first()


# news_type -> human label shown as the post-card category.
NEWS_TYPE_LABELS = {
    "blogpost": "Blog Post",
    "news": "News",
    "link": "Link",
    "video": "Video",
    "poll": "Poll",
}


def entry_to_post_dict(entry):
    """Shape a news Entry for the post card.

    Entry has no topic tag, so `category` comes from the news type and
    `tag` is omitted.
    """
    return {
        "title": entry.title,
        "url": entry.get_absolute_url(),
        "date": entry.publish_at,
        "category": NEWS_TYPE_LABELS.get(entry.tag, ""),
        "author": entry.author.to_v3_profile_dict(role="Author"),
    }


def posts_for_homepage(limit=5):
    entries = (
        Entry.objects.published()
        .filter(deleted_at__isnull=True)
        .select_related("author")
        .order_by("-publish_at")[:limit]
    )
    return [entry_to_post_dict(entry) for entry in entries]
