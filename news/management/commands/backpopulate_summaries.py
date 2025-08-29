import djclick as click
from news.models import Entry
from news.tasks import summary_dispatcher


@click.command()
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show which entries would be processed without actually dispatching tasks",
)
def command(dry_run):
    """Backpopulate summary field for news entries where summary is not set."""

    entries_without_summary = Entry.objects.filter(summary="")
    count = entries_without_summary.count()

    if count == 0:
        click.echo("No entries found without summaries.")
        return

    if dry_run:
        click.echo(f"Would process {count} entries:")
        for entry in entries_without_summary[:10]:
            click.echo(f"  - {entry.pk}: {entry.title}")
        if count > 10:
            click.echo(f"  ... and {count - 10} more")
        return

    click.echo(f"Processing {count} entries without summaries...")

    for entry in entries_without_summary:
        click.echo(f"Dispatching summary task for entry {entry.pk}: {entry.title}")
        summary_dispatcher.delay(entry.pk)

    click.echo(f"Dispatched summary tasks for {count} entries.")
