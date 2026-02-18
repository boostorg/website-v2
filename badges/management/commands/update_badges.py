import djclick as click

from badges.tasks import update_badges


@click.command()
def command():
    """Update or create Badge rows based on calculator classes.

    Triggers the badge update task asynchronously via Celery.
    """
    click.secho("Triggering badges update task...", fg="green")
    update_badges.delay()
    click.secho("Badges update task queued, output is in logging.", fg="green")
