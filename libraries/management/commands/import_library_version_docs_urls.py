import djclick as click

from django.conf import settings

from libraries.models import LibraryVersion
from libraries.tasks import get_and_store_library_version_documentation_urls_for_version
from versions.models import Version


@click.command()
@click.option(
    "--release",
    help="Boost version number (example: 1.81.0). If a partial version number is "
    "provided, the command process all versions that contain the partial version "
    "number (example: '--version='1.7' would process 1.7.0, 1.7.1, 1.7.2, etc.)",
)
@click.option(
    "--new",
    default=True,
    type=click.BOOL,
    help="True (default) Import library docs for newest version only from the db. False"
    " downloads docs for all versions",
)
@click.option(
    "--min-version",
    default=settings.MINIMUM_BOOST_VERSION,
    help="Minimum Boost version to process (default: 1.30.0)",
)
def command(release: str, new: bool, min_version: str):
    """Cycles through all Versions in the database, and for each version gets the
    corresponding tag's .gitmodules.

    The command then goes to the same tag of the repo for each library in the
    .gitmodules file and uses the information to create LibraryVersion instances, and
    add maintainers to LibraryVersions.

    Args:
        release (str): Boost version number (example: 1.81.0). If a partial version
            number is provided, the command process all versions that contain the
            partial version number (example: "--version="1.7" would process 1.70.0,
            1.70.1, 1.71.0, etc.)
        new (bool): If True (default), only imports library docs for the most recent
            version, if False it processes all versions greater than or equal to
            min_version. Overridden by --release if provided.
        min_version (str): Minimum Boost version to process.  If this is passed, then
            only versions that are greater than or equal to this version will be
            processed.
    """
    click.secho("Saving links to version-specific library docs...", fg="green")
    version_qs = (
        Version.objects.with_partials()
        .active()
        .filter(name__gte=f"boost-{min_version}")
    )
    if release:
        versions = version_qs.filter(name__icontains=release).order_by("-name")
    elif new:
        versions = [version_qs.most_recent()]
    else:
        versions = version_qs.order_by("-name")

    # For each version, get the library version documentation url paths
    for release in versions:
        click.echo(f"Processing version {release.name}...")
        try:
            get_and_store_library_version_documentation_urls_for_version(release.pk)
        except ValueError as e:
            click.secho(e, fg="red")
            continue

    for release in versions:
        library_versions = LibraryVersion.objects.filter(version=release)
        click.secho(f"Processing version {release.name}...", fg="green")
        for library_version in library_versions:
            if not library_version.documentation_url:
                click.secho(
                    f"Could not get docs url for {library_version.library.name} "
                    f"({release.name}).",
                    fg="red",
                )
                continue

    click.secho("Finished saving links to version-specific library docs.", fg="green")
