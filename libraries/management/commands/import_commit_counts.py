import djclick as click
from django.utils import timezone
from dateutil.relativedelta import relativedelta

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
    click.secho("Importing library commit history...", fg="green")
    client = GithubAPIClient(token=token)
    updater = LibraryUpdater(client=client)

    # We import the most recent year of commit history
    now = timezone.now()
    # Set 'since' to the first day of the month, 12 months ago
    since = timezone.make_aware(
        timezone.datetime(year=now.year - 1, month=now.month, day=1)
    )
    # Set 'until' to the last day of last month
    until = timezone.make_aware(
        timezone.datetime(year=now.year, month=now.month, day=1)
    ) - relativedelta(days=1)

    for library in Library.objects.all():
        updater.update_monthly_commit_counts(
            library, branch=branch, since=since, until=until
        )
        library.refresh_from_db()
        click.secho(
            f"Updated {library.name} commits; {library.commit_data.count()} monthly "
            f"counts added",
            fg="green",
        )

    click.secho("Finished importing library commit history", fg="green")
