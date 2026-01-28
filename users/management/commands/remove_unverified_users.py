import djclick as click

from users.tasks import remove_unverified_users


@click.command()
def command():
    """Remove unverified users that are candidates for deletion."""
    click.echo("Starting remove_unverified_users task...")

    try:
        result = remove_unverified_users.delay()
        click.secho(f"Task queued with ID: {result.id}", fg="green")
    except Exception as e:
        click.secho(f"Error: {e}", fg="red")
