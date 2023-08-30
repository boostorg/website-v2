import djclick as click

from libraries.github import LibraryUpdater
from core.githubhelper import GithubAPIClient
from libraries.models import Library


@click.command()
@click.option("--token", is_flag=False, help="Github API token")
@click.option(
    "--branch", is_flag=False, help="Branch name (default master)", default="master"
)
def command(branch, token):
    """Imports commit counts for all libraries, broken down by month, and saves
    them to the database. This is a one-time import.

    :param branch: The branch to import commit data from. Default is master.
    :param token: Github API token
    """
    updater = LibraryUpdater(client=GithubAPIClient(token=token))

    for library in Library.objects.all():
        updater.update_monthly_commit_counts(library, branch=branch)
        library.refresh_from_db()
        click.secho(
            f"Updated {library.name} commits; {library.commit_data.count()} monthly "
            f"counts added",
            fg="green",
        )
