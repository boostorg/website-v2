import djclick as click

from django.conf import settings

from versions.models import Version
from versions.tasks import import_library_versions


@click.command()
@click.option("--token", help="Github API token")
@click.option("--release", help="Boost version number (example: 1.81.0)")
@click.option(
    "--new",
    default=True,
    type=click.BOOL,
    help="Update only the library versions for the most recent version (default: True)."
    " False processes library versions for all versions greater than or equal to"
    " min-release.",
)
@click.option(
    "--min-release",
    default=settings.MINIMUM_BOOST_VERSION,
    help="Minimum Boost version to process (default: 1.31.0)",
)
def command(min_release: str, release: str, new: bool, token: str):
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
        new (bool): If True (default), only imports library versions for the most recent
        version, if False it processes all versions greater than or equal to min_release
        Overridden by --release if provided.
    """
    click.secho("Saving library-version relationships...", fg="green")
    versions_qs = (
        Version.objects.with_partials()
        .active()
        .filter(name__gte=f"boost-{min_release}")
    )
    if release:
        versions = versions_qs.filter(name__icontains=release).order_by("-name")
    elif new:
        versions = [versions_qs.most_recent()]
    else:
        versions = versions_qs.order_by("-name")

    for version in versions:
        version_type = "branch" if version.slug in settings.BOOST_BRANCHES else "tag"
        click.secho(f"Saving libraries for version {version.name}", fg="green")
        import_library_versions.delay(
            version.name, token=token, version_type=version_type
        )

    click.secho("Finished saving library-version relationships.", fg="green")
