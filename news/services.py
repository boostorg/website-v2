from pages.models import PostPage
from pages.routing import v3_posts_active

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


# The canonical "post card" dict shape lives on the models themselves:
# `Entry.to_v3_post_card_dict()` and `PostPage.to_v3_post_card_dict()` both
# return it, so downstream templates never branch on which one produced it.


def _latest_posts(limit: int, request):
    """Newest published posts, from whichever model the `v3` flag selects."""
    if v3_posts_active(request):
        from pages.models import PostPage

        return (
            PostPage.objects.live()
            .select_related("owner", "owner__displayed_profile_role_library")
            # The card links the author's profile, which reads their routing keys.
            .prefetch_related("owner__profile_routing_keys")
            .order_by("-first_published_at")[:limit]
        )
    return (
        Entry.objects.published()
        .filter(deleted_at__isnull=True)
        .select_related("author", "author__displayed_profile_role_library")
        # The card links the author's profile, which reads their routing keys.
        .prefetch_related("author__profile_routing_keys")
        .order_by("-publish_at")[:limit]
    )


def get_latest_post_cards(limit: int = 3, request=None) -> list[dict]:
    """Return the most recent published posts as v3 post-card dicts.

    Shared by the Learn page, library detail, community page, and any other
    surface that renders the v3 latest-posts card. Both models implement
    `to_v3_post_card_dict()`, so the card shape cannot drift between them.

    The source is picked by the `v3` waffle flag: Wagtail post pages when V3
    is on, legacy news entries when it is off. The two are never mixed, so
    turning the flag off puts every surface back on legacy content.
    """
    return [post.to_v3_post_card_dict() for post in _latest_posts(limit, request)]
