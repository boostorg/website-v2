import djclick as click

from libraries.github import LibraryUpdater


@click.command()
def command():
    l = LibraryUpdater()
    l.update_libraries()
