import djclick as click

from libraries.github import LibraryUpdater


@click.command()
def command():
    updater = LibraryUpdater()
    updater.update_libraries()
