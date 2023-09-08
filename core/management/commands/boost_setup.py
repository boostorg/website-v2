import djclick as click

from django.conf import settings
from django.core.management import call_command
from django.utils import timezone


@click.command()
@click.option("--token", is_flag=False, help="Github API token")
def command(token):
    """Calls all commands needed to set up the Boost database for the first time."""
    start = timezone.now()
    if not token:
        token = settings.GITHUB_TOKEN

    click.secho("Importing versions...", fg="green")
    call_command("import_versions", "--token", token)
    click.secho("Finished importing versions.", fg="green")

    click.secho("Importing libraries...", fg="green")
    call_command("update_libraries", "--token", token)
    click.secho("Finished importing libraries.", fg="green")

    click.secho("Saving library-version relationships...", fg="green")
    call_command("import_library_versions", "--token", token)
    click.secho("Finished saving library-version relationships.", fg="green")

    click.secho("Adding library maintainers...", fg="green")
    call_command("update_maintainers")
    click.secho("Finished adding library maintainers.", fg="green")

    click.secho("Adding library authors...", fg="green")
    call_command("update_authors")
    click.secho("Finished adding library authors.", fg="green")

    click.secho("Importing library commit history...", fg="green")
    call_command("import_commit_counts", "--token", token)
    click.secho("Finished importing library commit history.", fg="green")

    end = timezone.now()
    click.secho(f"All done! Completed in {end - start}", fg="green")
