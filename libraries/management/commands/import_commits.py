import djclick as click
from libraries.github import LibraryUpdater
from libraries.models import Library


@click.command()
@click.option("--key", is_flag=False, help="Library Key", default=None)
@click.option("--clean", is_flag=True, help="Library Key", default=False)
def command(key, clean):
    updater = LibraryUpdater()
    click.secho("Importing individual library commits...", fg="green")
    if key is None:
        for library in Library.objects.all():
            click.secho(f"Importing commits for {library}")
            updater.update_commits(library, clean=clean)
        updater.update_commit_author_github_data()
    else:
        library = Library.objects.get(key=key)
        updater.update_commits(library, clean=clean)
        updater.update_commit_author_github_data(obj=library)
    click.secho("Finished importing individual library commits.", fg="green")
