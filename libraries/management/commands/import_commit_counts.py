import djclick as click

from libraries.github import GithubAPIClient, LibraryUpdater
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
        commits = updater.client.get_commits(
            repo_slug=library.github_repo, branch=branch
        )
        commit_data = updater.parser.get_commits_per_month(commits)
        updater.update_monthly_commit_data(library, commit_data, branch=branch)
        library.refresh_from_db()
        click.secho(
            f"Updated {library.name} commits; {library.commit_data.count()} monthly "
            f"counts added",
            fg="green",
        )
