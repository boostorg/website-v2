import djclick as click

from libraries.tasks import synchronize_commit_author_user_data


@click.command()
def command():
    """
    Link contributors to users by either email or github username from the commitauthor
    records in the database.

    The referencing in the app is done through the github_username field from the
    CommitAuthor instance to the User model so we set that value.
    """
    click.secho("Linking contributors to users", fg="blue")
    synchronize_commit_author_user_data.delay()
    click.secho("Linking contributors to users has been queued.", fg="green")
