from badges.display import active_badges_prefetch
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
            # Badges per card, and the author's routing keys for the profile
            # link: one query for the page rather than one per card.
            .prefetch_related(
                active_badges_prefetch("owner__badges"),
                "owner__profile_routing_keys",
            )
            .order_by("-first_published_at")[:limit]
        )
    return (
        Entry.objects.published()
        .filter(deleted_at__isnull=True)
        .select_related("author", "author__displayed_profile_role_library")
        # Badges per card, and the author's routing keys for the profile link:
        # one query for the page rather than one per card.
        .prefetch_related(
            active_badges_prefetch("author__badges"),
            "author__profile_routing_keys",
        )
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
