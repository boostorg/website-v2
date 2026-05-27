"""Adapters turning backend data into V3 homepage template context."""

from news.models import Entry

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
