import requests
import structlog
from django.conf import settings

from news.models import Entry
from reports.constants import WEB_ANALYTICS_API_URL_V2, WEB_ANALYTICS_DOMAIN

logger = structlog.get_logger(__name__)

LEGACY_NEWS_ENTRY_PREFIX = "/news/entry/"
NEWS_ENTRY_PREFIX = "/news/"

# Routes that live under /news/ but are not posts. Without this every hit on
# e.g. /news/add/ would be recorded as views for a post slugged "add".
RESERVED_NEWS_SEGMENTS = frozenset(
    {"entry", "add", "moderate", "blogpost", "link", "news", "poll", "video"}
)


def slug_from_path(path: str) -> str | None:
    """Post slug for a Plausible page path, or None if it is not a post.

    Handles both the legacy `/news/entry/<slug>/` and the V3 `/news/<slug>/`
    shapes, so view counts survive the switch-over.
    """
    if path.startswith(LEGACY_NEWS_ENTRY_PREFIX):
        remainder = path[len(LEGACY_NEWS_ENTRY_PREFIX) :]
    elif path.startswith(NEWS_ENTRY_PREFIX):
        remainder = path[len(NEWS_ENTRY_PREFIX) :]
    else:
        return None

    slug = remainder.strip("/")
    if not slug or "/" in slug or slug in RESERVED_NEWS_SEGMENTS:
        return None
    return slug


def fetch_post_views() -> dict[str, int]:
    """Return a slug-to-pageviews mapping fetched from Plausible API v2.

    Returns an empty dict if the API key is not configured or the response
    contains no matching URLs.
    Raises requests.HTTPError on a non-2xx response.
    """
    if not settings.PLAUSIBLE_STATS_KEY or settings.PLAUSIBLE_STATS_KEY == "changeme":
        logger.info(
            "fetch_post_views.skipped", reason="PLAUSIBLE_STATS_KEY not configured"
        )
        return {}

    payload = {
        "site_id": WEB_ANALYTICS_DOMAIN,
        "metrics": ["pageviews"],
        "dimensions": ["event:page"],
        "filters": [["contains", "event:page", [NEWS_ENTRY_PREFIX]]],
        "date_range": "all",
    }
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": f"Bearer {settings.PLAUSIBLE_STATS_KEY}",
    }

    response = requests.post(
        url=WEB_ANALYTICS_API_URL_V2, json=payload, headers=headers
    )
    if not response.ok:
        raise requests.HTTPError(
            f"Plausible API error {response.status_code}: {response.text}",
            response=response,
        )

    data = response.json()
    if not data or "results" not in data:
        raise ValueError(f"Unexpected Plausible API response: {data}")

    slug_views: dict[str, int] = {}
    for result in data["results"]:
        slug = slug_from_path(result["dimensions"][0])
        if not slug:
            continue
        # A post can be hit under both its legacy and its V3 path; those are
        # the same post, so their view counts add up rather than overwrite.
        slug_views[slug] = slug_views.get(slug, 0) + int(result["metrics"][0])

    return slug_views


def update_page_views(slug_views: dict[str, int], entries: list | None = None) -> int:
    """Bulk-update Entry.page_views from a slug-to-count mapping.

    Returns the number of entries updated.
    """
    if not slug_views:
        return 0

    if entries is None:
        entries = list(Entry.objects.filter(slug__in=slug_views.keys()))
    unmatched = set(slug_views) - {e.slug for e in entries}
    if unmatched:
        logger.warning("update_page_views.unmatched_slugs", slugs=sorted(unmatched))

    for entry in entries:
        entry.page_views = slug_views[entry.slug]

    Entry.objects.bulk_update(entries, ["page_views"])
    return len(entries)


def update_post_page_views(slug_views: dict[str, int]) -> int:
    """Bulk-update PostPage.page_views from the same slug-to-count mapping.

    `PostPage.objects.ranked()` orders the V3 homepage posts card, so the
    Wagtail pages need the same view counts the legacy entries get; otherwise
    the ranking freezes at whatever the conversion command copied over.
    """
    if not slug_views:
        return 0

    from pages.models import PostPage

    pages = list(PostPage.objects.filter(slug__in=slug_views.keys()))
    for page in pages:
        page.page_views = slug_views[page.slug]

    PostPage.objects.bulk_update(pages, ["page_views"])
    return len(pages)
