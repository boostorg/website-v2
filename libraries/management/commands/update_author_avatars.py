import djclick as click
from libraries.github import LibraryUpdater
from libraries.models import Library


@click.command()
@click.option("--key", is_flag=False, help="Library Key", default=None)
@click.option("--clean", is_flag=True, help="Library Key", default=False)
def command(key, clean):
    updater = LibraryUpdater()
    click.secho("Updating author avatars from github...", fg="green")
    if key is None:
        updater.update_author_avatars(overwrite=clean)
    else:
        library = Library.objects.get(key=key)
        updater.update_author_avatars(obj=library, overwrite=clean)
    click.secho("Finished updating author avatars from github...", fg="green")
