from .models import Entry


def _entry_to_post_card(entry: Entry) -> dict:
    author = entry.author
    return {
        "title": entry.title,
        "url": entry.get_absolute_url(),
        "date": entry.publish_at,
        "category": entry.determined_news_type or "news",
        "tag": "",
        "author": {
            "name": getattr(author, "display_name", None) or str(author),
            "profile_url": None,
            "role": "Author",
            "avatar_url": (
                author.get_avatar_url() if hasattr(author, "get_avatar_url") else ""
            ),
            "badge_url": None,
            "show_badge": False,
        },
    }


def get_latest_post_cards(limit: int = 3) -> list[dict]:
    """Return the most recent published entries as v3 post-card dicts.

    Shared by the Learn page, library detail, community page, and any other
    surface that renders the v3 latest-posts card. Keeps the dict shape
    consistent so downstream templates don't drift.
    """
    queryset = (
        Entry.objects.published()
        .select_related("author")
        .order_by("-publish_at")[:limit]
    )
    return [_entry_to_post_card(entry) for entry in queryset]
