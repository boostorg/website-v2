import djclick as click

from libraries.updater import LibraryUpdater


@click.command()
@click.option("--local", is_flag=True, default=False)
@click.option("--token", is_flag=False, help="Github API token")
def command(local, token):
    """
    Calls the LibraryUpdater, which retrieves the active boost libraries
    from the Boost repo and updates the models in our database with the latest
    information on that library and related objects from GitHub.
    """
    updater = LibraryUpdater(token=token)
    updater.update_libraries()
