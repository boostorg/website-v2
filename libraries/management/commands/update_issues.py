from urllib.error import URLError
import djclick as click

from django.db import transaction

from libraries.github import LibraryUpdater
from libraries.models import Library


@click.command()
@click.option("--key", is_flag=False, help="Library Key", default=None)
@click.option("--clean", is_flag=True, help="Remove data before import?", default=False)
def command(key, clean):
    updater = LibraryUpdater()
    click.secho("Importing library issues...", fg="green")
    if key is None:
        libraries = Library.objects.all()
    else:
        libraries = [Library.objects.get(key=key)]

    for library in libraries:
        try:
            with transaction.atomic():
                if clean:
                    click.secho(f"Deleting issues for {library}")
                    library.issues.all().delete()
                click.secho(f"Importing issues for {library}")
                updater.update_issues(library)
        except URLError:
            click.secho(f"Error while importing issues for {library}.", fg="red")
            continue
    click.secho("Finished importing issues.", fg="green")
