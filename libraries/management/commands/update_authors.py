import djclick as click

from libraries.models import Library
from libraries.github import LibraryUpdater


@click.command()
@click.option("--library-name", is_flag=False, help="Library name (case-insensitive)")
def command(library_name):
    """Cycles through all Libraries in the database, and for each, uses the data
    in its `data` field to load the authors of that Library.

    Depends on the `data` field in the Library model containing an `authors` field. This
    data comes from the libraries.json file in the GitHub repo for the library at the
    `master` branch.

    If `--library-name` is specified, then only authors for that library will be loaded.
    """
    click.secho("Adding library authors...", fg="green")
    updater = LibraryUpdater()
    libraries = Library.objects.all()
    if library_name is not None:
        libraries = libraries.filter(library__name__iexact=library_name)

    for library in libraries.order_by("name"):
        if not library.data:
            continue

        updater.update_authors(library, authors=library.data.get("authors", []))

    click.secho("Finished adding library authors.", fg="green")
