import djclick as click

from libraries.tasks import update_commit_counts


@click.command()
@click.option("--token", is_flag=False, help="Github API token")
def command(token):
    """Imports commit counts for all libraries, broken down by month, and saves
    them to the database. This is a one-time import.

    :param token: Github API token
    """
    click.secho("Importing library commit history...", fg="green")
    update_commit_counts(token=token)
    click.secho("Finished importing library commit history", fg="green")
