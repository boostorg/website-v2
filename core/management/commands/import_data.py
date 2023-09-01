import djclick as click

from django.core.management import call_command


# Write a command that takes a --token option, a --verbose option, and a --local option.


@click.command()
@click.option("--verbose", is_flag=True, help="Enable verbose output.")
@click.option(
    "--local",
    is_flag=True,
    default=False,
    help="Local dev; import only what is necessary and mock the rest.",
)
@click.option("--token", is_flag=False, help="Github API token.")
def command(verbose, local, token):
    """
    Calls the necessary commands to set up the initial database of Boost version and
    library data.

    Functions:

    - Import official Boost release information from GitHub
    - Import official Boost library information from GitHub
    """
    # Load official Boost versions
    call_command("import_versions", token=token, verbose=verbose)

    # Load official Boost libraries
    call_command("update_libraries", token=token, local=local)
