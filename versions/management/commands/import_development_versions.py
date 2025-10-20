import djclick as click

from versions.tasks import import_development_versions


@click.command()
def command():
    """
    Import development versions from GitHub.

    This command will import the master and develop branches as versions
    from GitHub based on the BOOST_BRANCHES setting.
    """
    click.secho("Importing development versions...", fg="green")
    import_development_versions()
    click.secho("Finished importing development versions.", fg="green")
