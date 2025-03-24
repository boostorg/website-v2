import djclick as click

from users.tasks import update_users_githubs, update_commit_authors_users


@click.command()
def command():
    """
    Link contributors to users by either email or github username from the commitauthor
    records in the database.

    The referencing in the app is done through the github_username field from the
    CommitAuthor instance to the User model so we set that value.
    """
    click.secho("Linking contributors to users", fg="blue")
    update_users_githubs()
    update_commit_authors_users()
    click.secho("Finished linking contributors to users.", fg="green")
