import djclick as click

from django.conf import settings

from libraries.models import LibraryVersion
from libraries.tasks import get_and_store_library_version_documentation_urls_for_version
from versions.models import Version


@click.command()
@click.option(
    "--version",
    type=str,
    is_flag=False,
    help="Boost version number (example: 1.81.0). If a partial version number is "
    "provided, the command process all versions that contain the partial version "
    "number (example: '--version='1.7' would process 1.7.0, 1.7.1, 1.7.2, etc.)",
)
@click.option(
    "--min-version",
    type=str,
    default=settings.MINIMUM_BOOST_VERSION,
    help="Minimum Boost version to process (default: 1.30.0)",
)
def command(version, min_version):
    """Cycles through all Versions in the database, and for each version gets the
    corresponding tag's .gitmodules.

    The command then goes to the same tag of the repo for each library in the
    .gitmodules file and uses the information to create LibraryVersion instances, and
    add maintainers to LibraryVersions.

    Args:
        version (str): Boost version number (example: 1.81.0). If a partial version
            number is provided, the command process all versions that contain the
            partial version number (example: "--version="1.7" would process 1.70.0,
            1.70.1, 1.71.0, etc.)
        min_version (str): Minimum Boost version to process.  If this is passed, then
            only versions that are greater than or equal to this version will be
            processed.
    """
    click.secho("Saving links to version-specific library docs...", fg="green")
    min_version = f"boost-{min_version}"
    if version is None:
        versions = Version.objects.active().filter(name__gte=min_version)
    else:
        versions = Version.objects.filter(
            name__icontains=version, name__gte=min_version
        )

    # For each version, get the library version documentation url paths
    for version in versions.order_by("-name"):
        click.echo(f"Processing version {version.name}...")
        try:
            get_and_store_library_version_documentation_urls_for_version(version.pk)
        except ValueError as e:
            click.secho(e, fg="red")
            continue

    for version in versions.order_by("-name"):
        library_versions = LibraryVersion.objects.filter(version=version)
        click.secho(f"Processing version {version.name}...", fg="green")
        for library_version in library_versions:
            if not library_version.documentation_url:
                click.secho(
                    f"Could not get docs url for {library_version.library.name} "
                    f"({version.name}).",
                    fg="red",
                )
                continue

    click.secho("Finished saving links to version-specific library docs.", fg="green")
