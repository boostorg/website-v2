import djclick as click

from libraries.github import GithubAPIClient, GithubDataParser
from libraries.models import Library, LibraryVersion
from versions.models import Version


@click.command()
@click.option("--delete-versions", is_flag=True, help="Delete all existing versions")
@click.option(
    "--skip-existing-versions",
    is_flag=True,
    help="Skip versions that already exist in our database",
)
@click.option(
    "--delete-library-versions",
    is_flag=True,
    help="Delete all existing library versions",
)
@click.option(
    "--create-recent-library-versions",
    is_flag=True,
    help=(
        "Create library-versions for the most recent Boost version and each active "
        "Boost library"
    ),
)
@click.option("--token", is_flag=False, help="Github API token")
def command(
    delete_versions,
    skip_existing_versions,
    delete_library_versions,
    create_recent_library_versions,
    token,
):
    """Imports Boost release information from Github and updates the local database.

    The function retrieves Boost tags from the main Github repo, excluding beta releases
    and release candidates. For each tag, it fetches the associated data based on
    whether it's a full release (data in the tag) or not (data in the commit).

    It then creates or updates a Version instance in the local database for each tag.
    Depending on the options provided, it can also delete existing versions and library
    versions, and create new library versions for the most recent Boost version.

    Args:
        delete_versions (bool): If True, deletes all existing Version instances before
            importing.
        skip-existing-versions (bool): If True, skips versions that already exist in
            the database.
        delete_library_versions (bool): If True, deletes all existing LibraryVersion
            instances before importing.
        create_recent_library_versions (bool): If True, creates a LibraryVersion for
            each active Boost library and the most recent Boost version.
        token (str): Github API token, if you need to use something other than the
            setting.
    """
    # Delete Versions and LibraryVersions based on options
    if delete_versions:
        Version.objects.all().delete()
        click.echo("Deleted all existing versions.")

    if delete_library_versions:
        LibraryVersion.objects.all().delete()
        click.echo("Deleted all existing library versions.")

    # Get all Boost tags from Github
    client = GithubAPIClient(token=token)
    tags = client.get_tags()
    for tag in tags:
        name = tag["name"]

        # If we already have this version, skip importing it
        if skip_existing_versions and Version.objects.filter(name=name).exists():
            click.echo(f"Skipping {name}, already exists in database")
            continue

        # Skip beta releases, release candidates, etc.
        if any(["beta" in name.lower(), "-rc" in name.lower()]):
            click.echo(f"Skipping {name}, not a full release")
            continue

        tag_data = client.get_tag_by_name(name)

        version_data = None
        parser = GithubDataParser()
        if tag_data:
            # This is a tag and a release, so the metadata is in the tag itself
            version_data = parser.parse_tag(tag_data)
        else:
            # This is a tag, but not a release, so the metadata is in the commit
            commit_data = client.get_commit_by_sha(commit_sha=tag["commit"]["sha"])
            version_data = parser.parse_commit(commit_data)

        if not version_data:
            click.echo(f"Skipping {name}, no version data found")
            continue

        version, _ = Version.objects.update_or_create(name=name, defaults=version_data)
        click.echo(f"Saved version {version.name}. Created: {_}")

    if create_recent_library_versions:
        # Associate existing Libraries with the most recent LibraryVersion
        version = Version.objects.most_recent()
        for library in Library.objects.all():
            library_version, _ = LibraryVersion.objects.get_or_create(
                library=library, version=version
            )
            click.echo(f"Saved library version {library_version}. Created: {_}")
