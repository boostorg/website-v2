from datetime import datetime, timezone as dt_timezone

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count

from badges.display import active_badges_prefetch
from pages.routing import v3_posts_active


from .constants import BYPASS_DESCRIPTION_LIMIT_PERMISSION
from .models import (
    AIDescriptionSettings,
    DescriptionGenerationAttempt,
    DescriptionGenerationOutcome,
    Entry,
)

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


class DescriptionQuotaExceeded(Exception):
    """Raised when a user has spent their daily description generations."""

    def __init__(self, used, limit):
        self.used = used
        self.limit = limit
        super().__init__(f"{used}/{limit} description generations used today")


def utc_day_start():
    """Midnight UTC for the current day.

    Computed against UTC explicitly rather than via `timezone.now()` so a future
    change to `TIME_ZONE` can't silently move when the limit resets.
    """
    return datetime.now(dt_timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )


def counted_attempts_today():
    """Attempts since midnight UTC that consumed a generation.

    Rejections never reached the model, so they don't count against anyone's
    quota - they're recorded only so the cap can be tuned from real usage.
    """
    return DescriptionGenerationAttempt.objects.filter(
        created_at__gte=utc_day_start()
    ).exclude(outcome=DescriptionGenerationOutcome.RATE_LIMITED)


def is_exempt_from_description_limit(user):
    """Whether `user` skips the daily cap.

    Backed by a permission rather than a group name so superusers pass without
    a special case and a group rename in the admin can't quietly disable it.
    """
    return user.has_perm(f"news.{BYPASS_DESCRIPTION_LIMIT_PERMISSION}")


def _record_rejection(user, input_type, input_size):
    """Log a refused generation so the cap can be tuned from real usage."""
    DescriptionGenerationAttempt.objects.create(
        user=user,
        input_type=input_type,
        input_size=input_size,
        outcome=DescriptionGenerationOutcome.RATE_LIMITED,
    )


def ensure_description_generation_quota(request, input_type, input_size=0):
    """Refuse an exhausted user before an expensive step, without reserving.

    For callers that have to do real work - an outbound fetch, an extraction -
    before they know the input size the reservation needs. Raises
    `DescriptionQuotaExceeded` when the user is already out of generations, so
    a spent user cannot loop that work for free.

    Advisory only, and not a substitute for
    `consume_description_generation_quota`: nothing is reserved here, so two
    concurrent requests can both pass this check. The reservation is still what
    settles the count.
    """
    user = request.user
    if is_exempt_from_description_limit(user):
        return

    limit = AIDescriptionSettings.load(request_or_site=request).daily_limit
    used = counted_attempts_today().filter(user=user).count()
    if used >= limit:
        _record_rejection(user, input_type, input_size)
        raise DescriptionQuotaExceeded(used=used, limit=limit)


def consume_description_generation_quota(request, input_type, input_size):
    """Reserve one of today's generations for the requesting user.

    Returns the `DescriptionGenerationAttempt` reserved for this call, which the
    caller must resolve to a final outcome. Raises `DescriptionQuotaExceeded`
    when the user is out of generations.

    The count and the insert share a transaction holding a lock on the user row,
    so two concurrent requests from a scripted loop serialize instead of both
    reading a stale count. The lock is released before the model call, never
    held across it.
    """
    user = request.user
    limit = AIDescriptionSettings.load(request_or_site=request).daily_limit
    used = None

    with transaction.atomic():
        if not is_exempt_from_description_limit(user):
            # Result deliberately discarded: this is here to take a row lock,
            # so a second concurrent request for the same user waits instead of
            # counting the same stale total.
            get_user_model().objects.select_for_update().filter(pk=user.pk).first()
            used = counted_attempts_today().filter(user=user).count()

        if used is None or used < limit:
            return DescriptionGenerationAttempt.objects.create(
                user=user,
                input_type=input_type,
                input_size=input_size,
                outcome=DescriptionGenerationOutcome.PENDING,
            )

    # Recorded outside the block above: raising inside it would roll the
    # rejection row straight back out again, and the rejection count is what
    # the cap gets tuned from.
    _record_rejection(user, input_type, input_size)
    raise DescriptionQuotaExceeded(used=used, limit=limit)


def description_generation_limit_reached(request):
    """Whether the requesting user has already spent today's generations.

    Drives the create-post page's exhausted state on load. It is a hint for the
    UI only - the endpoints enforce the limit themselves, so a stale or forged
    page can't buy an extra generation.
    """
    user = request.user
    if not user.is_authenticated or is_exempt_from_description_limit(user):
        return False
    limit = AIDescriptionSettings.load(request_or_site=request).daily_limit
    return counted_attempts_today().filter(user=user).count() >= limit


def description_generation_usage_today():
    """Today's generation counts, for the Wagtail settings panel."""
    day_start = utc_day_start()
    return {
        "generations": counted_attempts_today().count(),
        "users_at_limit": DescriptionGenerationAttempt.objects.filter(
            created_at__gte=day_start,
            outcome=DescriptionGenerationOutcome.RATE_LIMITED,
        ).aggregate(users=Count("user", distinct=True))["users"],
    }
