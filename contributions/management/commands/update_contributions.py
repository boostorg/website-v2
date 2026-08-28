import djclick as click

from contributions.tasks import update_contributions


@click.command()
@click.option(
    "--github-token",
    help="Optional GitHub API token (defaults to system token)",
    default=None,
)
def command(github_token):
    """Update the contributions list for all versions.

    This command iterates through all versions and updates their contribution
    data from GitHub. If no token is provided, it uses the system default token.
    """
    click.secho("Starting contributions update...", fg="green")
    update_contributions.delay(github_token=github_token)

    click.secho("Contributions update queued!", fg="green")
