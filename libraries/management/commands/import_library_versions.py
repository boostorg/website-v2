import djclick as click
import requests

from django.conf import settings

from libraries.github import LibraryUpdater
from core.githubhelper import GithubAPIClient, GithubDataParser
from libraries.models import Library, LibraryVersion
from libraries.tasks import get_and_store_library_version_documentation_urls_for_version
from versions.models import Version


@click.command()
@click.option("--token", is_flag=False, help="Github API token")
@click.option("--release", is_flag=False, help="Boost version number (example: 1.81.0)")
@click.option(
    "--min-release",
    type=str,
    default=settings.MINIMUM_BOOST_VERSION,
    help="Minimum Boost version to process (default: 1.31.0)",
)
def command(min_release, release, token):
    """Cycles through all Versions in the database, and for each version gets the
    corresponding tag's .gitmodules.

    The command then goes to the same tag of the repo for each library in the
    .gitmodules file and uses the information to create LibraryVersion instances, and
    add maintainers to LibraryVersions.

    Note: This command takes 30-60 minutes when the database is empty.

    Args:
        token (str): Github API token, if a value other than the setting is needed.
        release (str): Boost version number (example: 1.81.0). If a partial version
            number is provided, the command process all versions that contain the
            partial version number (example: "--version="1.7" would process 1.7.0,
            1.7.1, 1.7.2, etc.)
    """
    click.secho("Saving library-version relationships...", fg="green")
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
        ref = client.get_ref(ref=f"tags/{version.name}")
        raw_gitmodules = client.get_gitmodules(ref=ref)
        if not raw_gitmodules:
            skipped.append(
                {"version": version.name, "reason": "Invalid gitmodules file"}
            )
            continue

        gitmodules = parser.parse_gitmodules(raw_gitmodules.decode("utf-8"))

        for gitmodule in gitmodules:
            reason = ""
            library_name = gitmodule["module"]

            click.echo(f"Processing module {library_name}...")

            if library_name in updater.skip_modules:
                continue

            try:
                libraries_json = client.get_libraries_json(
                    repo_slug=library_name, tag=version.name
                )
            except requests.exceptions.JSONDecodeError:
                reason = "libraries.json file was invalid"
            except requests.exceptions.HTTPError:
                reason = "libraries.json file not found"
            except Exception as e:
                reason = str(e)

            if not libraries_json:
                # Can happen with older releases
                library_version = save_library_version_by_library_key(
                    library_name, version, gitmodule
                )
                if library_version:
                    if not reason:
                        reason = "failure with libraries.json file"
                    click.secho(f"{library_name} ({version.name} saved.", fg="green")
                    continue
                else:
                    if not reason:
                        reason = """
                            Could not find libraries.json file, and could not find
                            library by gitmodule name
                        """
                    skipped.append(
                        {
                            "version": version.name,
                            "library": library_name,
                            "reason": reason,
                        }
                    )
                    continue

            libraries = (
                libraries_json if isinstance(libraries_json, list) else [libraries_json]
            )
            parsed_libraries = [parser.parse_libraries_json(lib) for lib in libraries]
            for lib_data in parsed_libraries:
                library, created = Library.objects.get_or_create(
                    key=lib_data["key"],
                    defaults={
                        "name": lib_data.get("name"),
                        "description": lib_data.get("description"),
                        "cpp_standard_minimum": lib_data.get("cxxstd"),
                        "data": lib_data,
                    },
                )
                library_version, _ = LibraryVersion.objects.update_or_create(
                    version=version, library=library, defaults={"data": lib_data}
                )
                click.secho(f"{library.name} ({version.name} saved)", fg="green")
                # if created and not library.github_url:
                if not library.github_url:
                    pass
                #     # todo: handle this. Need a github_url for these.

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

    click.secho("Finished saving library-version relationships.", fg="green")


def save_library_version_by_library_key(library_key, version, gitmodule={}):
    """Saves a LibraryVersion instance by library key and version."""
    try:
        library = Library.objects.get(key=library_key)
        library_version, _ = LibraryVersion.objects.update_or_create(
            version=version, library=library, defaults={"data": gitmodule}
        )
        return library_version
    except Library.DoesNotExist:
        return
