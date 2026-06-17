from .models import Entry

# Display labels for a post's type "chip" (the small category label on post
# cards and headers). Maps a raw news_type/tag to a human-facing label; anything
# not listed is title-cased. Single source of truth so the label can't drift
# between the post-card service, the community page, and the news detail view.
NEWS_TYPE_LABELS = {"blogpost": "Blog"}


def news_type_label(news_type: str) -> str:
    """Human-facing label for a post's type chip (e.g. 'blogpost' -> 'Blog')."""
    news_type = (news_type or "news").lower()
    return NEWS_TYPE_LABELS.get(news_type, news_type.capitalize())


# The canonical "post card" dict shape consumed by the v3 latest-posts card.
# Every content source (news Entry models today, Wagtail pages later) must map
# into this same shape so downstream templates don't have to branch on origin:
#
#     {
#         "title": str,
#         "url": str,
#         "date": datetime,          # used to sort across sources
#         "category": str,
#         "tag": str,
#         "author": {
#             "name": str,
#             "profile_url": str | None,
#             "role": str,
#             "avatar_url": str,
#             "badge_url": str | None,
#         },
#     }


def _entry_to_post_card(entry: Entry) -> dict:
    author = entry.author
    return {
        "title": entry.title,
        "url": entry.get_absolute_url(),
        "date": entry.publish_at,
        "category": news_type_label(entry.determined_news_type),
        "tag": "",
        "author": {
            "name": getattr(author, "display_name", None) or str(author),
            "profile_url": None,
            "role": author.role,
            "avatar_url": (
                author.get_avatar_url() if hasattr(author, "get_avatar_url") else ""
            ),
            "badge_url": None,
        },
    }


def _get_entry_post_cards(limit: int) -> list[dict]:
    """Latest published news Entry models as post-card dicts."""
    queryset = (
        Entry.objects.published()
        .filter(deleted_at__isnull=True)
        .select_related("author")
        .order_by("-publish_at")[:limit]
    )
    return [_entry_to_post_card(entry) for entry in queryset]


def _get_wagtail_post_cards(limit: int) -> list[dict]:
    """Latest published Wagtail page posts as post-card dicts.

    Stub for the planned migration of post content onto Wagtail pages (per the
    earlier discussion about authoring posts as pages rather than Entry models).
    No post-style Wagtail page model exists yet, so this returns nothing and the
    Learn/community/library surfaces fall back to Entry data only.

    When the page model lands, query its published pages here and map each into
    the post-card shape via a `_wagtail_page_to_post_card(page)` helper. Because
    `get_latest_post_cards` already merges and re-sorts every source by date,
    wiring this up requires no changes at the call sites.
    """
    return []


def get_latest_post_cards(limit: int = 3) -> list[dict]:
    """Return the most recent published posts as v3 post-card dicts.

    Shared by the Learn page, library detail, community page, and any other
    surface that renders the v3 latest-posts card. Keeps the dict shape
    consistent so downstream templates don't drift.

    Aggregates across content sources (news Entry models today, Wagtail pages
    once that lands), merges them, and returns the newest `limit` overall.
    """
    cards = _get_entry_post_cards(limit) + _get_wagtail_post_cards(limit)
    cards.sort(key=lambda card: card["date"], reverse=True)
    return cards[:limit]
