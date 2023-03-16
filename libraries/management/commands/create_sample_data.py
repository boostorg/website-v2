import djclick as click
from faker import Faker

from django.contrib.auth import get_user_model

from libraries.models import Library, LibraryVersion, Category, PullRequest, Issue
from versions.models import Version


fake = Faker()
User = get_user_model()

USER_COUNT = 100


@click.command()
@click.option('--all', is_flag=True)
@click.option('--drop', is_flag=True)
@click.option('--users', is_flag=True)
@click.option('--versions', is_flag=True)
@click.option('--categories', is_flag=True)
@click.option('--libraries', is_flag=True)
@click.option('--library_versions', is_flag=True)
@click.option('--authors', is_flag=True)
@click.option('--maintainers', is_flag=True)
@click.option('--prs', is_flag=True)
@click.option('--issues', is_flag=True)
def command(all, drop, users, versions, libraries, library_versions, authors, maintainers, prs, issues, categories):
    """
    Populate the database with fake data for local development.

    --all: If True, run all methods including the drop command.
    --drop: If True, drop all records in the database.
    --users: If True, create fake users.
    --versions: If True, create fake versions.
    --categories: If True, create fake categories.
    --libraries: If True, create fake libraries and assign them categories.
    --library_versions: If True or if both --libraries and --versions are True, create fake library versions.
    --authors: If True, add fake library authors.
    --maintainers: If True, add fake library version maintainers.
    --prs: If True, add fake library pull requests.
    --issues: If True, add fake library issues.
    """

    if all:
        call_all()
        return

    if drop:
        drop_all_records()

    if users:
        create_users(USER_COUNT)

    if versions:
        create_versions(10)

    if categories:
        create_categories(20)

    if libraries:
        create_libraries(50)
        assign_library_categories()

    if library_versions:
        create_library_versions()
    else:
        if libraries and versions:
            create_library_versions()

    if authors:
        create_authors()

    if maintainers:
        create_maintainers()

    if prs:
        create_pull_requests(10)

    if issues:
        create_issues(10)


def call_all():
    drop_all_records()
    create_users(USER_COUNT)
    create_versions(10)
    create_categories(20)
    create_libraries(50)
    create_library_versions()
    create_authors()
    create_maintainers()
    create_pull_requests(10)
    create_issues(10)


def create_users(count):
    click.echo("Creating users...")


def create_versions(count):
    click.echo("Creating versions...")


def create_libraries(count):
    click.echo("Creating libraries...")


def assign_library_categories():
    click.secho("Assigning categories to libraries...")


def create_library_versions():
    click.echo("Creating library versions...")


def create_authors():
    click.echo("Adding library authors...")


def create_maintainers():
    click.echo("Adding library version maintainers...")


def create_pull_requests(count):
    click.echo("Adding library pull requests...")


def create_issues(count):
    click.echo("Adding library issues...")


def create_categories(count):
    click.echo("Adding categories...")


def drop_all_records():
    click.echo("Dropping all records...")
