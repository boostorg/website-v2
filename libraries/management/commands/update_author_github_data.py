import djclick as click
from libraries.github import LibraryUpdater
from libraries.models import Library


@click.command()
@click.option("--key", is_flag=False, help="Library Key", default=None)
@click.option("--clean", is_flag=True, help="Library Key", default=False)
def command(key, clean):
    updater = LibraryUpdater()
    click.secho(
        "Updating author avatars from github. This may take a while, depending on how many authors need to be updated...",
        fg="green",
    )
    if key is None:
        updater.update_commit_author_github_data(overwrite=clean)
    else:
        library = Library.objects.get(key=key)
        updater.update_commit_author_github_data(obj=library, overwrite=clean)
    click.secho("Finished updating author avatars from github...", fg="green")
