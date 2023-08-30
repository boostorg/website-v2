import djclick as click

from libraries.github import LibraryUpdater
from core.githubhelper import GithubAPIClient
from libraries.models import Library


@click.command()
@click.option(
    "--library", is_flag=False, help="Name of library (example: Accumulators)"
)
@click.option(
    "--limit",
    is_flag=False,
    type=int,
    help="Number of libraries to update (example: 10)",
)
@click.option("--token", is_flag=False, help="Github API token")
def command(token, library, limit):
    """Fetch and update the date of the first GitHub tag for a given library.

    If no library is specified, fetch data for all libraries.

    It uses the GitHub API to fetch the tag data, and you may pass your own token.

    The command updates the `first_github_tag_date` field of each library.
    After the update, it prints out the library name and the date of the first tag.
    If no tags were found for a library, it prints a warning message.

    Arguments:
    token: str, optional -- The GitHub API token for authentication. Default value is
        set in the client class.
    library: str, optional -- The name of the library for which to fetch the tag data.
        If not provided, the command fetches data for all libraries. Case-insensitive.
    limit: int, optional -- The number of libraries to update. If not provided, the
        command updates all libraries. If this is not passed, this command can take a
        long time to run.
    """
    client = GithubAPIClient(token=token)
    updater = LibraryUpdater(client=client)

    if library:
        libraries = Library.objects.filter(name__iexact=library)
    else:
        libraries = Library.objects.filter(first_github_tag_date__isnull=True)

    if limit:
        libraries = libraries[: int(limit)]

    for library in libraries:
        updater.update_first_github_tag_date(library)

    for library in libraries:
        library.refresh_from_db()
        if library.first_github_tag_date:
            first_tag = library.first_github_tag_date.strftime("%m-%Y")
            click.secho(
                f"{library.name} - First tag: {first_tag}",
                fg="green",
            )
        else:
            click.secho(f"{library.name} - No tags found", fg="red")
