import djclick as click
from celery import group

from news.models import Video
from news.tasks import set_thumbnail_for_video_entry, set_thumbnail_for_video_page

from pages.models import PostPage


@click.command()
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show which entries would be processed without actually dispatching tasks",
)
def command(dry_run):
    """Backpopulate video entry thumbnails that have not been set"""

    v_qs = Video.objects.filter(thumbnail__isnull=True)
    p_qs = PostPage.objects.filter(
        video_thumbnail__isnull=True, content__0__type="video"
    )
    count = v_qs.count() + p_qs.count()

    if count == 0:
        click.echo("No entries found without thumbnails.")
        return

    if dry_run:
        click.echo(f"Would process {count} entries:")
        for entry in (list(v_qs) + list(p_qs))[:10]:
            click.echo(f"  - {entry.pk}: {entry.title}")
        if count > 10:
            click.echo(f"  ... and {count - 10} more")
        return

    click.echo("Dispatching thumbnail tasks...")
    g = group(set_thumbnail_for_video_entry.s(i.pk) for i in v_qs.iterator())
    g.apply_async()
    g_2 = group(set_thumbnail_for_video_page.s(i.pk) for i in p_qs.iterator())
    g_2.apply_async()
    click.echo(f"Thumbnail tasks for {count} tasks queued.")
