from badges.display import active_badges_prefetch
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


def _latest_posts(limit: int, request, library_slug=None):
    """Newest published posts, from whichever model the `v3` flag selects.

    `library_slug` narrows the result to posts tagged with that library.
    """
    if v3_posts_active(request):
        from pages.models import PostPage

        queryset = PostPage.objects.live()
        if library_slug is not None:
            # Posts are linked to a library through a `ContentTag` whose slug
            # mirrors the library slug (see the create-post view). The filter
            # goes through `tagged_items` rather than the `tags` manager: the
            # tag's parental key points at `wagtailcore.Page`, so filtering
            # `tags__slug` on a child page model builds a join against a
            # `pages_postpage.id` column that does not exist.
            queryset = queryset.filter(tagged_items__tag__slug=library_slug)
        return (
            queryset.select_related("owner", "owner__displayed_profile_role_library")
            # Badges per card, and the author's routing keys for the profile
            # link: one query for the page rather than one per card.
            .prefetch_related(
                active_badges_prefetch("owner__badges"),
                "owner__profile_routing_keys",
            ).order_by("-first_published_at")[:limit]
        )
    if library_slug is not None:
        # Legacy entries carry no library relation, so there is nothing to
        # filter on; showing them unfiltered would be worse than showing none.
        return Entry.objects.none()
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


def get_latest_post_cards(
    limit: int = 3, request=None, library_slug=None
) -> list[dict]:
    """Return the most recent published posts as v3 post-card dicts.

    Shared by the Learn page, library detail, community page, and any other
    surface that renders the v3 latest-posts card. Both models implement
    `to_v3_post_card_dict()`, so the card shape cannot drift between them.

    The source is picked by the `v3` waffle flag: Wagtail post pages when V3
    is on, legacy news entries when it is off. The two are never mixed, so
    turning the flag off puts every surface back on legacy content.

    Pass `library_slug` to get only the posts tagged with that library. Legacy
    entries have no library relation, so a library-scoped call returns an empty
    list when the flag is off rather than falling back to unfiltered posts.
    An empty list is also what hides the card on the library subpage.
    """
    return [
        post.to_v3_post_card_dict()
        for post in _latest_posts(limit, request, library_slug)
    ]
