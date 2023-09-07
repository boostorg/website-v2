import djclick as click


@click.command()
def command():
    """
    Sets up data for local development, including:

    - [ ] Importing live Boost versions from GitHub
    - [ ] Limiting to only the most recent N Boost versions
    - [ ] Generating fake VersionFiles
    - [ ] Importing live Boost libraries and categories from GitHub
    - [ ] Importing live LibraryVersions
    """
    click.echo("Hello, world!")
