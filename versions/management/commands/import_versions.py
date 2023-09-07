import djclick as click

from django.conf import settings
from django.core.management import call_command
from fastcore.xtras import obj2dict

from core.githubhelper import GithubAPIClient
from versions.models import Version
from versions.tasks import get_release_date_for_version


# Skip beta releases, release candidates, and pre-1.0 versions
EXCLUSIONS = ["beta", "-rc"]

# Base url to generate the GitHub release URL
BASE_GITHUB_URL = "https://github.com/boostorg/boost/releases/tag/"


@click.command()
@click.option("--verbose", is_flag=True, help="Enable verbose output.")
@click.option("--delete-versions", is_flag=True, help="Delete all existing versions")
@click.option("--token", is_flag=False, help="Github API token")
def command(
    verbose,
    delete_versions,
    token,
):
    """Imports Boost release information from Github and updates the local database.

    The function retrieves Boost tags from the main Github repo, excluding beta releases
    and release candidates.

    It then creates or updates a Version instance in the local database for each tag.

    Args:
        verbose (bool): Enable verbose output (show logging statements)
        delete_versions (bool): If True, deletes all existing Version instances before
            importing.
        token (str): Github API token, if you need to use something other than the
            setting.
    """
    if delete_versions:
        Version.objects.all().delete()
        click.echo("Deleted all existing versions.")

    # Get all Boost tags from Github
    client = GithubAPIClient(token=token)
    tags = client.get_tags()

    for tag in tags:
        name = tag["name"]
        if verbose:
            click.secho(f"Importing {name}...", fg="yellow")

        if skip_tag(name):
            continue

        # Save the Version object
        version, _ = Version.objects.update_or_create(
            name=name,
            defaults={"github_url": f"{BASE_GITHUB_URL}/{name}", "data": obj2dict(tag)},
        )

        # Load the release date if needed
        if not version.release_date:
            try:
                get_release_date_for_version.delay(
                    version.id, tag["commit"]["sha"], token=token
                )
            except Exception as e:
                click.secho(f"Failed to load release date for {name}: {e}", fg="red")

        # Load the release downloads
        add_release_downloads(version)

        click.secho(f"Saved version {version.name}. Created: {_}", fg="green")


def add_release_downloads(version):
    version_num = version.name.replace("boost-", "")
    if version_num < "1.63.0":
        return

    call_command("import_artifactory_release_data", release=version_num)


def skip_tag(name):
    """Returns True if the given tag should be skipped."""
    # If this version falls in our exclusion list, skip it
    if any(pattern in name.lower() for pattern in EXCLUSIONS):
        return True

    # If this version is too old, skip it
    version_num = name.replace("boost-", "")
    if version_num < settings.MINIMUM_BOOST_VERSION:
        return True

    return False
