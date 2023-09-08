import djclick as click

from libraries.models import LibraryVersion
from libraries.github import LibraryUpdater


@click.command()
@click.option("--library-name", is_flag=False, help="Library name (case-insensitive)")
@click.option("--release", is_flag=False, help="Boost version number (example: 1.81.0)")
def command(library_name, release):
    """Cycles through all LibraryVersions in the database, and for each version, uses
    the data in its `data` field to load the maintainers of that LibraryVersion (if
    they have not been loaded yet).

    Depends on the `data` field in the LibraryVersion model containing a `maintainers`
    field. This data comes from the libraries.json file in the GitHub repo for the
    library at the GitHub tag for that version.

    If `--release` is specified, then only maintainers for libraries in the specified
    release version will be loaded.

    If `--library-name` is specified, then only maintainers for libraries with that name
    will be loaded.
    """
    click.secho("Adding library maintainers...", fg="green")
    updater = LibraryUpdater()
    library_versions = LibraryVersion.objects.all()
    if library_name is not None:
        library_versions = library_versions.filter(library__name__iexact=library_name)

    if release is not None:
        library_versions = library_versions.filter(version__name__icontains=release)

    for library_version in library_versions.order_by(
        "-version__name", "-library__name"
    ):
        if not library_version.data:
            continue

        updater.update_maintainers(
            library_version, maintainers=library_version.data.get("maintainers", [])
        )

    click.secho("Finished adding library maintainers.", fg="green")
