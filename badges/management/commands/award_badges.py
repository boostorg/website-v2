import djclick as click
from django.contrib.auth import get_user_model

from badges.tasks import award_badges

User = get_user_model()


@click.command()
@click.option(
    "--user-email",
    type=str,
    default=None,
    help="Specific user email to calculate badges for. If not provided, calculates for all users.",
)
def command(user_email):
    """Calculate and award badges to users based on their contributions."""
    user_id = None

    if user_email:
        try:
            user_id = User.objects.values_list("id", flat=True).get(email=user_email)
        except User.DoesNotExist:
            click.secho(f"User with {user_email=} doesn't exist", fg="red")
            return
    if user_id:
        click.secho(f"Calculating badges for {user_email}...", fg="green")
    else:
        click.secho("Calculating badges for all users...", fg="green")
    award_badges.delay(user_id)
    click.secho("Award badges task queued, output is in logging.", fg="green")
