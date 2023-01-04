import djclick as click

from libraries.github import LibraryUpdater


@click.command()
def command():
    """
    Calls the LibraryUpdater, which retrieves the active boost libraries
    from the Boost repo and updates the models in our database with the latest
    information on that library (repo) and its issues, pull requests, and related
    objects from GitHub.
    """
    updater = LibraryUpdater()
    updater.update_libraries()
