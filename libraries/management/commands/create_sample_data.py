import djclick as click
from datetime import timedelta
from faker import Faker
from itertools import cycle
from model_bakery import baker
from random import randint, choice

from django.contrib.auth import get_user_model
from django.utils import timezone

from libraries.models import Library, LibraryVersion, Category, PullRequest, Issue
from versions.models import Version


fake = Faker()
User = get_user_model()

USER_COUNT = 100

BOOST_CATEGORIES = [
    "Algorithms",
    "Assertions",
    "Build",
    "Collections",
    "Concept Checking",
    "Concurrency",
    "Config",
    "Conversion",
    "Coroutines",
    "DLL",
]


BOOST_LIBRARIES = [
    "algorithm",
    "asio",
    "assign",
    "circular_buffer",
    "date_time",
    "filesystem",
    "graph",
    "iostreams",
    "lexical_cast",
    "math",
    "program_options",
    "regex",
    "serialization",
    "signals2",
    "system",
    "thread",
    "uuid",
]


BOOST_VERSIONS = [
    "1.81.0",
    "1.80.0",
    "1.79.1",
    "1.79.0",
    "1.78.2",
    "1.78.1",
    "1.78.0",
    "1.77.1",
    "1.77.0",
    "1.76.1",
]


@click.command()
@click.option("--all", is_flag=True)
@click.option("--drop", is_flag=True)
@click.option("--users", is_flag=True)
@click.option("--versions", is_flag=True)
@click.option("--categories", is_flag=True)
@click.option("--libraries", is_flag=True)
@click.option("--library_versions", is_flag=True)
@click.option("--authors", is_flag=True)
@click.option("--maintainers", is_flag=True)
@click.option("--prs", is_flag=True)
@click.option("--issues", is_flag=True)
def command(
    all,
    drop,
    users,
    versions,
    libraries,
    library_versions,
    authors,
    maintainers,
    prs,
    issues,
    categories,
):
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
        create_versions()

    if categories:
        create_categories()

    if libraries:
        create_libraries()
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
        create_pull_requests()

    if issues:
        create_issues()


def call_all():
    drop_all_records()
    create_users(USER_COUNT)
    create_versions()
    create_categories()
    create_libraries()
    assign_library_categories()
    create_library_versions()
    create_authors()
    create_maintainers()
    create_pull_requests()
    create_issues()


def create_users(count):
    """Creates fake users"""
    click.secho("Creating users...")

    first_names = [fake.first_name() for i in range(1, count)]
    last_names = [fake.last_name() for i in range(1, count)]

    objects = baker.make(
        User,
        _quantity=count,
        first_name=cycle(first_names),
        last_name=cycle(last_names),
    )
    click.secho(f"...Created {len(objects)} users", fg="green")
    return objects


def create_versions():
    """
    Creates fake versions using the names in BOOST_VERSIONS, and sets
    their release dates at every 180 days
    """
    click.secho("Creating versions...")
    release_dates = get_dates()
    objects = baker.make(
        Version,
        _quantity=len(BOOST_VERSIONS),
        name=cycle(BOOST_VERSIONS),
        release_date=cycle(release_dates),
    )
    click.secho(f"...Created {len(objects)} versions", fg="green")
    return objects


def create_libraries():
    """Creates fake libraries using the names in BOOST_LIBRARIES"""
    click.secho("Creating libraries...")
    objects = baker.make(
        Library, _quantity=len(BOOST_LIBRARIES), name=cycle(BOOST_LIBRARIES)
    )
    click.secho(f"...Created {len(objects)} versions", fg="green")
    return objects


def assign_library_categories():
    """Assigns 1-3 categories to each library"""
    click.secho("Assigning categories to libraries...")
    for library in Library.objects.all():
        if library.categories.count() > 1:
            continue

        count = randint(1, 3)
        categories = Category.objects.order_by("?")[:count]
        for category in categories:
            library.categories.add(category)
            click.secho(f"...{library} assigned the {category} category", fg="green")


def create_library_versions():
    """Assigns a random number of versions to each library"""
    click.secho("Creating library versions...")
    for library in Library.objects.all():
        start_version = Version.objects.order_by("?").first()
        for version in Version.objects.filter(
            release_date__gt=start_version.release_date
        ):
            lib_version, created = LibraryVersion.objects.get_or_create(
                library=library, version=version
            )
            click.secho(f"...{lib_version} created", fg="green")


def create_authors():
    """Assigns 1-3 authors to each library"""
    click.secho("Adding library authors...")
    for library in Library.objects.all():
        count = randint(1, 3)
        authors = User.objects.filter(is_superuser=False).order_by("?")[:count]
        for author in authors:
            library.authors.add(author)
            click.secho(f"...{author} assigned as {library} author", fg="green")


def create_maintainers():
    """Assigns 1-3 maintainers to each Library for the most recent version only"""
    click.secho("Adding library version maintainers...")
    version = Version.objects.most_recent()
    for library in Library.objects.all():
        try:
            library_version = LibraryVersion.objects.get(
                version=version, library=library
            )
        except LibraryVersion.DoesNotExist:
            continue

        count = randint(1, 3)
        maintainers = User.objects.filter(is_superuser=False).order_by("?")[:count]
        for maintainer in maintainers:
            library_version.maintainers.add(maintainer)
            click.secho(
                f"...{maintainer} assigned as {library_version} maintainer", fg="green"
            )


def create_pull_requests():
    """Creates 5-10 PRs for each library"""
    click.secho("Adding library pull requests...")
    for library in Library.objects.all():
        count = randint(5, 10)
        titles = [
            fake.sentence(nb_words=4, variable_nb_words=True, ext_word_list=None)
            for i in range(1, count)
        ]
        dates = [get_random_date() for i in range(1, count)]
        numbers = [randint(5000, 9999) for i in range(1, count)]
        is_open = [choice([True, False]) for i in range(1, count)]
        objects = baker.make(
            PullRequest,
            _quantity=count,
            library=library,
            title=cycle(titles),
            is_open=cycle(is_open),
            created=cycle(dates),
            number=cycle(numbers),
        )
        click.secho(
            f"...{len(objects)} pull requests created for {library}", fg="green"
        )


def create_issues():
    """Creates 5-10 PRs for each library"""
    click.secho("Adding library issues...")
    for library in Library.objects.all():
        count = randint(5, 10)
        titles = [
            fake.sentence(nb_words=4, variable_nb_words=True, ext_word_list=None)
            for i in range(1, count)
        ]
        dates = [get_random_date() for i in range(1, count)]
        numbers = [randint(5000, 9999) for i in range(1, count)]
        is_open = [choice([True, False]) for i in range(1, count)]
        objects = baker.make(
            Issue,
            _quantity=count,
            library=library,
            title=cycle(titles),
            is_open=cycle(is_open),
            created=cycle(dates),
            number=cycle(numbers),
        )
        click.secho(f"...{len(objects)} issues created for {library}", fg="green")


def create_categories():
    """Create categories using BOOST_CATEGORIES"""
    objects = baker.make(
        Category, _quantity=len(BOOST_CATEGORIES), name=cycle(BOOST_CATEGORIES)
    )
    click.secho(f"...Created {len(objects)} categories", fg="green")
    return objects


def drop_all_records():
    """Drop every table"""
    click.secho("Dropping all records...", fg="red")

    click.secho("Dropping Non-Superusers...", fg="red")
    User.objects.filter(is_superuser=False).delete()

    click.secho("Dropping LibraryVersions...", fg="red")
    LibraryVersion.objects.all().delete()

    click.secho("Dropping Versions...", fg="red")
    Version.objects.all().delete()

    click.secho("Dropping Categories...", fg="red")
    Category.objects.all().delete()

    click.secho("Dropping PullRequests...", fg="red")
    PullRequest.objects.all().delete()

    click.secho("Dropping Issues...", fg="red")
    Issue.objects.all().delete()

    click.secho("Dropping Libraries...", fg="red")
    Library.objects.all().delete()


def get_dates(count=0):
    """
    Returns a list of dates, in descending order, starting with today and
    decrementing by 180 days
    """
    if not count:
        count = len(BOOST_VERSIONS)

    dates = []
    for i in range(count):
        date = timezone.now().date() - timedelta(days=180 * i)
        dates.append(date)

    return dates


def get_random_date():
    """Returns a date within the last 5 years"""
    start_date = timezone.now() - timedelta(days=365 * 5)
    return fake.date_between(start_date=start_date, end_date="today")
