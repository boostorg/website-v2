import djclick as click

from django.conf import settings

from versions.models import Version
from versions.tasks import import_library_versions


@click.command()
@click.option("--token", is_flag=False, help="Github API token")
@click.option("--release", is_flag=False, help="Boost version number (example: 1.81.0)")
@click.option(
    "--min-release",
    type=str,
    default=settings.MINIMUM_BOOST_VERSION,
    help="Minimum Boost version to process (default: 1.31.0)",
)
def command(min_release, release, token):
    """Cycles through all Versions in the database, and for each version gets the
    corresponding tag's .gitmodules.

    The command then goes to the same tag of the repo for each library in the
    .gitmodules file and uses the information to create LibraryVersion instances, and
    add maintainers to LibraryVersions.

    Note: This command takes 30-60 minutes when the database is empty.

    Args:
        token (str): Github API token, if a value other than the setting is needed.
        release (str): Boost version number (example: 1.81.0). If a partial version
            number is provided, the command process all versions that contain the
            partial version number (example: "--version="1.7" would process 1.7.0,
            1.7.1, 1.7.2, etc.)
    """
    click.secho("Saving library-version relationships...", fg="green")

    min_release = f"boost-{min_release}"
    if release is None:
        versions = Version.objects.active().filter(name__gte=min_release)
    else:
        versions = Version.objects.filter(
            name__icontains=release, name__gte=min_release
        )

    for version in versions.order_by("-name"):
        click.secho(f"Saving libraries for version {version.name}", fg="green")
        import_library_versions.delay(version.name, token=token)

    click.secho("Finished saving library-version relationships.", fg="green")
