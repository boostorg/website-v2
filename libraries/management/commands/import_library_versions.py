import djclick as click

from libraries.github import GithubAPIClient, GithubDataParser, LibraryUpdater
from libraries.models import Library, LibraryVersion
from versions.models import Version


@click.command()
@click.option("--token", is_flag=False, help="Github API token")
@click.option("--release", is_flag=False, help="Boost version number (example: 1.81.0)")
def command(release, token):
    """Cycles through all Versions in the database, and for each version gets the
    corresponding tag's .gitmodules.

    The command then goes to the same tag of the repo for each library in the
    .gitmodules file and uses the information to create LibraryVersion instances, and
    add maintainers to LibraryVersions.

    Args:
        token (str): Github API token, if you need to use something other than the setting.
        release (str): Boost version number (example: 1.81.0). If a partial version number is
        provided, the command process all versions that contain the partial version number
        (example: "--version="1.7" would process 1.7.0, 1.7.1, 1.7.2, etc.)
    """
    client = GithubAPIClient(token=token)
    parser = GithubDataParser()
    updater = LibraryUpdater(client=client)

    skipped = []

    if release is not None:
        versions = Version.objects.filter(name__icontains=release)
    else:
        versions = Version.objects.active()

    for version in versions:
        click.echo(f"Processing version {version.name}...")

        # Get the .gitmodules for the version using the version name, which is also the git tag
        ref = client.get_ref(ref=version.name)
        try:
            raw_gitmodules = client.get_gitmodules(ref=ref)
        except Exception:
            # Only happens for one version; uncertain why.
            click.secho(f"Could not get gitmodules for {version.name}.", fg="red")
            skipped.append(
                {"version": version.name, "reason": "Could not get gitmodules"}
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

            # If the libraries.json file exists, we can use it to get the library info
            if libraries_json:
                if isinstance(libraries_json, list):
                    libraries = [
                        parser.parse_libraries_json(lib) for lib in libraries_json
                    ]
                else:
                    libraries = [parser.parse_libraries_json(libraries_json)]

                for lib_data in libraries:
                    try:
                        library = Library.objects.get(name=lib_data["name"])
                    except Library.DoesNotExist:
                        click.echo(
                            f"Could not find library by gitmodule name; skipping {library_name}"
                        )
                        skipped.append(
                            {
                                "version": version.name,
                                "library": library_name,
                                "reason": "Could not find library by gitmodule name",
                            }
                        )
                    else:
                        library_version, _ = LibraryVersion.objects.get_or_create(
                            version=version, library=library
                        )
                        click.echo(
                            f"Saved library version {library_version}. Created? {_}"
                        )
                        updater.update_maintainers(
                            library_version, maintainers=lib_data["maintainers"]
                        )
                        click.secho(
                            f"Updated maintainers for {library_version}.", fg="green"
                        )

                    click.echo(f"Saved library version {library_version}.")
            else:
                # This can happen with older tags; the libraries.json file didn't always exist, so
                # when it isn't present, we search for the library by the module name and try to save
                # the LibraryVersion that way.
                click.echo(
                    f"Could not get libraries.json for {library_name}; will try to save by gitmodule name."
                )
                try:
                    library = Library.objects.get(name=library_name)
                except Library.DoesNotExist:
                    click.echo(
                        f"Could not find library by gitmodule name; skipping {library_name}"
                    )
                    skipped.append(
                        {
                            "version": version.name,
                            "library": library_name,
                            "reason": "Could not find library in database by gitmodule name",
                        }
                    )
                else:
                    library_version, _ = LibraryVersion.objects.get_or_create(
                        version=version, library=library
                    )
                    click.echo(f"Saved library version {library_version}. Created? {_}")

    for skipped_obj in skipped or []:
        if "library" in skipped_obj:
            click.secho(
                f"Skipped {skipped_obj['library']} in {skipped_obj['version']}: {skipped_obj['reason']}",
                fg="red",
            )
        else:
            click.secho(
                f"Skipped {skipped_obj['version']}: {skipped_obj['reason']}",
                fg="red",
            )
