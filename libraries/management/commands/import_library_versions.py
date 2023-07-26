import djclick as click

from libraries.github import GithubAPIClient, GithubDataParser, LibraryUpdater
from libraries.models import Library, LibraryVersion
from libraries.tasks import get_and_store_library_version_documentation_urls_for_version
from libraries.utils import parse_date
from versions.models import Version


@click.command()
@click.option("--token", is_flag=False, help="Github API token")
@click.option("--release", is_flag=False, help="Boost version number (example: 1.81.0)")
@click.option(
    "--min-release",
    type=str,
    default="1.81.0",
    help="Minimum Boost version to process (default: 1.30.0)",
)
def command(min_release, release, token):
    """Cycles through all Versions in the database, and for each version gets the
    corresponding tag's .gitmodules.

    The command then goes to the same tag of the repo for each library in the
    .gitmodules file and uses the information to create LibraryVersion instances, and
    add maintainers to LibraryVersions.

    Args:
        token (str): Github API token, if a value other than the setting is needed.
        release (str): Boost version number (example: 1.81.0). If a partial version
            number is provided, the command process all versions that contain the
            partial version number (example: "--version="1.7" would process 1.7.0,
            1.7.1, 1.7.2, etc.)
    """
    client = GithubAPIClient(token=token)
    parser = GithubDataParser()
    updater = LibraryUpdater(client=client)

    skipped = []

    min_release = f"boost-{min_release}"
    if release is None:
        versions = Version.objects.active().filter(name__gte=min_release)
    else:
        versions = Version.objects.filter(
            name__icontains=release, name__gte=min_release
        )

    for version in versions.order_by("-name"):
        click.echo(f"Processing version {version.name}...")

        click.secho(f"Saving library versions for {version.name}...", fg="yellow")
        ref = client.get_ref(ref=f"tags/{version.name}")
        raw_gitmodules = client.get_gitmodules(ref=ref)
        if not raw_gitmodules:
            click.secho(f"Could not get gitmodules for {version.name}.", fg="red")
            skipped.append(
                {"version": version.name, "reason": "Invalid gitmodules file"}
            )
            continue

        gitmodules = parser.parse_gitmodules(raw_gitmodules.decode("utf-8"))

        for gitmodule in gitmodules:
            library_name = gitmodule["module"]

            click.echo(f"Processing module {library_name}...")

            if library_name in updater.skip_modules:
                click.echo(f"Skipping module {library_name}.")
                continue

            libraries_json = client.get_libraries_json(repo_slug=library_name)

            # Some specific library-versions (Hana v1.65.0, for example) require
            # the "url" field from the .gitmodules file to be used instead of the
            # module name, so we try the module name first, and if that doesn't
            # work, we try the url.
            github_data = client.get_repo(repo_slug=library_name)

            if not github_data:
                github_data = client.get_repo(repo_slug=gitmodule["url"])

            if github_data:
                extra_data = {
                    "last_github_update": parse_date(github_data.get("updated_at", "")),
                    "github_url": github_data.get("html_url", ""),
                }
            else:
                skipped.append(
                    {
                        "version": version.name,
                        "library": library_name,
                        "reason": "Not skipped, but data is incomplete",
                    }
                )
                extra_data = {}

            # If the libraries.json file exists, we can use it to get the library info
            if libraries_json:
                libraries = (
                    libraries_json
                    if isinstance(libraries_json, list)
                    else [libraries_json]
                )
                parsed_libraries = [
                    parser.parse_libraries_json(lib) for lib in libraries
                ]
                for lib_data in parsed_libraries:
                    lib_data.update(extra_data)
                    library = updater.update_library(lib_data)
                    library_version = handle_library_version(
                        version, library, lib_data["maintainers"], updater
                    )
                    if not library_version:
                        click.secho(
                            f"Could not save library version {lib_data['name']}.",
                            fg="red",
                        )
                        skipped.append(
                            {
                                "version": version.name,
                                "library": lib_data["name"],
                                "reason": "Could not save library version",
                            }
                        )
            else:
                # This can happen with older tags; the libraries.json file didn't always
                # exist, so when it isn't present, we search for the library by the
                # module name and try to save the LibraryVersion that way.
                click.echo(
                    f"Could not get libraries.json for {lib_data['name']}; will try to "
                    f"save by gitmodule name."
                )
                try:
                    library = Library.objects.get(name=lib_data["name"])
                    library_version = handle_library_version(
                        version, library, [], updater
                    )
                except Library.DoesNotExist:
                    click.secho(
                        f"Could not save library version {lib_data['name']}.", fg="red"
                    )
                    skipped.append(
                        {
                            "version": version.name,
                            "library": lib_data["name"],
                            "reason": "Could not save library version",
                        }
                    )
                    continue

        # Retrieve and store the docs url for each library-version in this release
        get_and_store_library_version_documentation_urls_for_version.delay(version.pk)

    skipped_messages = [
        f"Skipped {obj['library']} in {obj['version']}: {obj['reason']}"
        if "library" in obj
        else f"Skipped {obj['version']}: {obj['reason']}"
        for obj in skipped
    ]

    for message in skipped_messages:
        click.secho(message, fg="red")


def handle_library_version(version, library, maintainers, updater):
    """Handles the creation and updating of a LibraryVersion instance."""
    library_version, created = LibraryVersion.objects.get_or_create(
        version=version, library=library
    )
    click.secho(
        f"Saved library version {library_version}. Created? {created}", fg="green"
    )

    if created:
        updater.update_maintainers(library_version, maintainers=maintainers)
        click.secho(f"Updated maintainers for {library_version}.", fg="green")

    return library_version
