import djclick as click

from libraries.github import LibraryUpdater


@click.command()
@click.option("--local", is_flag=True, default=False)
@click.option("--update_monthly_commit_counts", is_flag=True, default=True)
@click.option("--update_first_tag_date", is_flag=True, default=True)
def command(local, update_monthly_commit_counts, update_first_tag_date):
    """
    Calls the LibraryUpdater, which retrieves the active boost libraries
    from the Boost repo and updates the models in our database with the latest
    information on that library (repo) and its issues, pull requests, and related
    objects from GitHub.

    If the --local flag is set, then the monthly commit counts and first tag date
    will not be updated. This is useful for testing, since the monthly commit counts
    and first tag date are not updated very often, and it takes a long time to
    retrieve them from GitHub.

    If the --update_monthly_commit_counts flag is set, then the monthly commit counts
    will be updated. This can take a long time.

    If the --update_first_tag_date flag is set, then the first tag date will be updated.
    This can take a long time.
    """
    updater = LibraryUpdater()

    if local:
        update_monthly_commit_counts = False
        update_first_tag_date = False
    updater.update_libraries(
        update_monthly_commit_counts=update_monthly_commit_counts,
        update_first_tag_date=update_first_tag_date,
    )
