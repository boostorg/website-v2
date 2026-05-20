import djclick as click
import requests
import structlog
from django.conf import settings

from news.models import Entry
from reports.constants import WEB_ANALYTICS_API_URL_V2, WEB_ANALYTICS_DOMAIN

logger = structlog.get_logger()

NEWS_ENTRY_PREFIX = "/news/entry/"


@click.command()
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be updated without writing to the database",
)
def command(dry_run):
    """Sync per-post page view counts from Plausible into Entry.page_views."""

    if not settings.PLAUSIBLE_STATS_KEY or settings.PLAUSIBLE_STATS_KEY == "changeme":
        click.echo("PLAUSIBLE_STATS_KEY is not configured, skipping.")
        return

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
        raise click.ClickException(
            f"Plausible API error {response.status_code}: {response.text}"
        )
    data = response.json()

    if not data or "results" not in data:
        raise ValueError(f"Unexpected Plausible API response: {data}")

    # Build slug → view_count mapping from API results
    slug_views: dict[str, int] = {}
    for result in data["results"]:
        path = result["dimensions"][0]
        if not path.startswith(NEWS_ENTRY_PREFIX):
            continue
        # Strip prefix and trailing slash to get the slug
        slug = path[len(NEWS_ENTRY_PREFIX) :].rstrip("/")
        if slug:
            slug_views[slug] = int(result["metrics"][0])

    if not slug_views:
        click.echo("No matching post URLs returned by Plausible.")
        return

    entries = Entry.objects.filter(slug__in=slug_views.keys())
    matched = {e.slug: e for e in entries}
    unmatched = set(slug_views) - set(matched)

    if unmatched:
        logger.warning("sync_post_views.unmatched_slugs", slugs=sorted(unmatched))

    if dry_run:
        click.echo(f"Would update {len(matched)} entries (dry run):")
        for slug, entry in matched.items():
            click.echo(f"  {slug}: {entry.page_views} → {slug_views[slug]}")
        return

    for entry in matched.values():
        entry.page_views = slug_views[entry.slug]

    Entry.objects.bulk_update(matched.values(), ["page_views"])
    click.echo(f"Updated page_views for {len(matched)} entries.")
