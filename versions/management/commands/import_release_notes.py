import djclick as click

from versions.tasks import import_release_notes


@click.command()
@click.option("--new", default=True, help="Only import notes for new versions")
def command(new: bool):
    """
    Import and process release notes for all available versions.
    """

    click.secho("Importing release notes...", fg="green")
    import_release_notes.delay(new_versions_only=new)
