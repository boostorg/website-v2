import djclick as click
import requests

from news.plausible import (
    fetch_post_views,
    update_page_views,
    update_post_page_views,
)
from news.models import Entry


@click.command()
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be updated without writing to the database",
)
def command(dry_run):
    """Sync per-post page view counts from Plausible.

    Writes to both `Entry.page_views` and `PostPage.page_views` so the legacy
    and V3 popularity rankings stay in step regardless of the flag.
    """

    try:
        slug_views = fetch_post_views()
    except (requests.HTTPError, ValueError) as e:
        raise click.ClickException(str(e)) from e

    if not slug_views:
        click.echo("No matching post URLs returned by Plausible.")
        return

    entries = list(Entry.objects.filter(slug__in=slug_views.keys()))
    matched = {e.slug: e for e in entries}

    if dry_run:
        click.echo(f"Would update {len(matched)} entries (dry run):")
        for slug, entry in matched.items():
            click.echo(f"  {slug}: {entry.page_views} -> {slug_views[slug]}")
        return

    updated = update_page_views(slug_views, entries=entries)
    click.echo(f"Updated page_views for {updated} entries.")

    updated_pages = update_post_page_views(slug_views)
    click.echo(f"Updated page_views for {updated_pages} Wagtail post pages.")
