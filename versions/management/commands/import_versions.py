import djclick as click

from versions.tasks import import_versions


@click.command()
@click.option("--delete-versions", is_flag=True, help="Delete all existing versions")
@click.option("--new", is_flag=True, help="Only import new versions")
@click.option("--token", is_flag=False, help="Github API token")
def command(
    delete_versions,
    new,
    token,
):
    """Imports Boost release information from Github and updates the local database.

    The function retrieves Boost tags from the main Github repo, excluding beta releases
    and release candidates.

    It then creates or updates a Version instance in the local database for each tag.

    Args:
        verbose (bool): Enable verbose output (show logging statements)
        delete_versions (bool): If True, deletes all existing Version instances before
            importing.
        token (str): Github API token, if you need to use something other than the
            setting.
    """
    click.secho("Importing versions...", fg="green")
    import_versions.delay(
        delete_versions=delete_versions, new_versions_only=new, token=token
    )
    click.secho("Finished importing versions.", fg="green")
