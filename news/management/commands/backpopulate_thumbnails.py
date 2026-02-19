import djclick as click
from celery import group

from news.models import Video
from news.tasks import set_thumbnail_for_video_entry


@click.command()
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show which entries would be processed without actually dispatching tasks",
)
def command(dry_run):
    """Backpopulate video entry thumbnails that have not been set"""

    qs = Video.objects.filter(thumbnail__isnull=True)
    count = qs.count()

    if count == 0:
        click.echo("No entries found without thumbnails.")
        return

    if dry_run:
        click.echo(f"Would process {count} entries:")
        for entry in qs[:10]:
            click.echo(f"  - {entry.pk}: {entry.title}")
        if count > 10:
            click.echo(f"  ... and {count - 10} more")
        return

    click.echo("Dispatching thumbnail tasks...")
    g = group(set_thumbnail_for_video_entry.s(i.pk) for i in qs.iterator())
    g.apply_async()
    click.echo(f"Thumbnail tasks for {count} tasks queued.")
