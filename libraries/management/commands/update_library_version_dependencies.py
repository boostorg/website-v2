import djclick as click

from libraries.github import LibraryUpdater


@click.command()
@click.option("--token", is_flag=False, help="Github API token")
@click.option(
    "--owner",
    is_flag=False,
    help="The repo owner of the artifact to be parsed for dependencies.",
)
@click.option("--clean", is_flag=True, help="Remove dependencies before adding them.")
def command(token=None, owner=None, clean=False):
    click.secho(
        "Attempting to update library version dependencies",
        fg="green",
    )
    updater = LibraryUpdater(token=token)
    updater.update_library_version_dependencies(owner=owner, clean=clean)
    click.secho("Finished importing libraries.", fg="green")
