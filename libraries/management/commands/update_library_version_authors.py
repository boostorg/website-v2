import djclick as click

from django.db import transaction

from libraries.models import Library, LibraryVersion
from libraries.github import LibraryUpdater


def release_version_names(release):
    """The version names ``--release`` should be read as, or an empty set.

    Callers say "1.92.0" and callers say "boost-1.92.0"; the admin passes the
    stored name and an operator types the number. Both are matched exactly, so a
    release cannot quietly widen into its neighbours the way a substring match
    would turn "1.9" into 1.90, 1.91 and 1.92.
    """
    if not release:
        return set()
    bare = release.removeprefix("boost-")
    return {release, bare, f"boost-{bare}"}


@click.command()
@click.option("--library-name", is_flag=False, help="Library name (case-insensitive)")
@click.option(
    "--release",
    is_flag=False,
    help="Boost version to limit the run to (example: 1.92.0)",
)
@click.option("--clean", is_flag=True, help="Clear authors before importing new ones?")
def command(library_name, release, clean):
    """Cycles through all LibrariesVersions in the database, and for each,
    uses the data in its `data` field to load the authors of that LibraryVersion.

    Depends on the `data` field in the LibraryVersion model containing an `authors`
    field. This data comes from the libraries.json file in the GitHub repo for
    the library at the version.name ref tag.

    If `--library-name` is specified, then only authors for that library will be loaded.
    If `--release` is specified, then only authors for that version will be loaded, and
    the retroactive backfill is skipped: a run scoped to one release must not reach
    into the releases either side of it.
    If `--clean` is specified, then authors will be removed before being added back in.
    """
    click.secho("Adding libraryVersion authors...", fg="green")
    updater = LibraryUpdater()
    libraries = Library.objects.all()
    if library_name is not None:
        libraries = libraries.filter(name__iexact=library_name)

    version_names = release_version_names(release)
    library_versions = LibraryVersion.objects.filter(library__in=libraries)
    if version_names:
        library_versions = library_versions.filter(version__name__in=version_names)

    with transaction.atomic():
        for library_version in library_versions.select_related(
            "library", "version"
        ).order_by("library__name", "version__name"):
            if not library_version.data:
                continue

            if clean:
                library_version.authors.clear()
            updater.update_authors(
                library_version,
                authors=library_version.data.get("authors", []),
            )

        # Only for a sweep. The backfill copies a newer release's authors onto an
        # older one, so running it after a single-release pass would push that
        # release's authors backwards over versions that are already correct.
        if not version_names:
            for library in libraries.order_by("name").prefetch_related(
                "library_version"
            ):
                retroactively_apply_authors_to_previous_versions(library)

    click.secho("Finished adding library version authors.", fg="green")


def retroactively_apply_authors_to_previous_versions(library):
    """If the current version does not have authors, but a future version does
    use the future version's authors for the previous version.

    """
    sorted_library_versions = sorted(
        library.library_version.all().select_related("version"),
        key=lambda x: x.version.name,
        reverse=True,
    )
    prev_authors = []
    for lv in sorted_library_versions:
        if not lv.authors.exists():
            lv.authors.add(*prev_authors)
        else:
            prev_authors = list(lv.authors.all())
