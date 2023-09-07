import djclick as click

from django.core.management import call_command


@click.command()
@click.option(
    "--max-version-count", type=int, default=100, help="Number of versions to import."
)
@click.option("--token", is_flag=False, help="Github API token")
def command(max_version_count, token):
    call_command("import_versions", token=token, max_count=max_version_count)
