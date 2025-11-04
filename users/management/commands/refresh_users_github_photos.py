import djclick as click
from django.contrib.auth import get_user_model

from users.tasks import refresh_users_github_photos

User = get_user_model()


@click.command()
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show which users would be updated without actually updating them",
    default=False,
)
def command(dry_run):
    """Refresh GitHub photos for all users who have a GitHub username.

    This command fetches the latest profile photo from GitHub for each user
    and updates their local profile image. This is useful for keeping user
    avatars up-to-date as users change their GitHub profile photos.

    When run without --dry-run, this calls the refresh_users_github_photos()
    Celery task which queues photo updates for all users with GitHub usernames.

    With --dry-run, displays information about which users would be updated
    without making any changes.
    """
    users = User.objects.exclude(github_username="")
    user_count = users.count()

    if dry_run:
        click.secho(f"Refreshing {user_count} users, Github users:", fg="yellow")
        for user in users:
            click.echo(f"  - User {user.pk}: {user.github_username}")
    else:
        click.secho(f"Refreshing photos, {user_count} users", fg="green")
        refresh_users_github_photos()
        click.secho(f"Triggered photo refresh task, {user_count} users", fg="green")
