import djclick as click

from versions.tasks import import_release_notes


@click.command()
def command():
    """
    Import and process release notes for all available versions.
    """

    click.secho("Importing release notes...", fg="green")
    import_release_notes.delay()
