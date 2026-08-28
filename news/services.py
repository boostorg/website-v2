from pages.models import PostPage

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
#             "tenure_stamp": dict | None,
#             "boost_day_stamp": dict | None,
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
            # profile_url settles every account state in one place: a claimed
            # account gets its profile, an unclaimed stub gets GitHub (its
            # profile page is an empty shell), a deactivated one gets nothing.
            "profile_url": getattr(author, "profile_url", None),
            "role": author.role,
            "avatar_url": (
                author.get_avatar_url() if hasattr(author, "get_avatar_url") else ""
            ),
            "tenure_stamp": getattr(author, "tenure_stamp", None),
            "boost_day_stamp": getattr(author, "boost_day_stamp", None),
            "badge_url": None,
        },
    }


def _get_entry_post_cards(limit: int) -> list[dict]:
    """Latest published news Entry models as post-card dicts."""
    queryset = (
        Entry.objects.published()
        .filter(deleted_at__isnull=True)
        .select_related("author")
        # The card links the author's profile, which reads their routing keys.
        .prefetch_related("author__profile_routing_keys")
        .order_by("-publish_at")[:limit]
    )
    return [_entry_to_post_card(entry) for entry in queryset]


def _get_wagtail_post_cards(limit: int) -> list[dict]:
    """Latest published Wagtail page posts as post-card dicts.

    Stub for the planned migration of post content onto Wagtail pages (per the
    earlier discussion about authoring posts as pages rather than Entry models).
    `PostPage` now exists, but the unfiltered surfaces (Learn, community,
    homepage) still read Entry data only, so this returns nothing until that
    cutover happens.

    To wire it up, query published `PostPage` rows here and map each one with
    `_post_page_to_post_card`. Because `get_latest_post_cards` already merges
    and re-sorts every source by date, that needs no changes at the call sites.
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


def _post_page_to_post_card(page: PostPage) -> dict:
    author = page.author
    return {
        "title": page.title,
        "url": page.get_absolute_url(),
        "date": page.first_published_at,
        "category": (
            news_type_label(page.post_content_type) if page.post_content_type else ""
        ),
        "tag": "",
        "author": author.to_v3_profile_dict() if author else None,
    }


def get_library_post_cards(library_slug: str, limit: int = 3) -> list[dict]:
    """Return the latest posts tagged with `library_slug` as post-card dicts.

    Posts are linked to a library through a `ContentTag` whose slug mirrors the
    library slug (see the create-post view). Only Wagtail `PostPage` posts carry
    that link; legacy news `Entry` rows have no library relation, so they are
    deliberately excluded rather than shown unfiltered.

    The filter goes through `tagged_items` rather than the `tags` manager: the
    tag's parental key points at `wagtailcore.Page`, so filtering `tags__slug`
    on a child page model builds a join against a `pages_postpage.id` column
    that does not exist.

    Returns an empty list when nothing is tagged, which is what hides the card.
    """
    if not library_slug:
        return []

    queryset = (
        PostPage.objects.live()
        .public()
        .filter(tagged_items__tag__slug=library_slug)
        .select_related("owner", "owner__displayed_profile_role_library")
        .order_by("-first_published_at")[:limit]
    )
    return [_post_page_to_post_card(page) for page in queryset]
