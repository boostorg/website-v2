import djclick as click

from django.db import transaction

from libraries.models import Library
from libraries.github import LibraryUpdater


@click.command()
@click.option("--library-name", is_flag=False, help="Library name (case-insensitive)")
@click.option("--clean", is_flag=True, help="Clear authors before importing new ones?")
def command(library_name, clean):
    """Cycles through all LibrariesVersions in the database, and for each,
    uses the data in its `data` field to load the authors of that LibraryVersion.

    Depends on the `data` field in the LibraryVersion model containing an `authors`
    field. This data comes from the libraries.json file in the GitHub repo for
    the library at the version.name ref tag.

    If `--library-name` is specified, then only authors for that library will be loaded.
    If `--clean` is specified, then authors will be removed before being added back in.
    """
    click.secho("Adding libraryVersion authors...", fg="green")
    updater = LibraryUpdater()
    libraries = Library.objects.all().prefetch_related("library_version")
    if library_name is not None:
        libraries = libraries.filter(library__name__iexact=library_name)

    with transaction.atomic():
        for library in libraries.order_by("name"):
            for library_version in library.library_version.all():
                if not library_version.data:
                    continue

                if clean:
                    library_version.authors.clear()
                updater.update_authors(
                    library_version,
                    authors=library_version.data.get("authors", []),
                )
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
