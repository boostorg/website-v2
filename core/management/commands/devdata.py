import djclick as click

from django.core.management import call_command


@click.command()
@click.option("--token", is_flag=False, help="Github API token")
def command(token):
    call_command("import_versions", token=token)
    pass