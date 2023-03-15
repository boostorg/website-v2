import djclick as click
import re
import structlog

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils.text import slugify

from libraries.github import LibraryUpdater
from libraries.models import Library, LibraryVersion
from versions.models import Version

logger = structlog.get_logger()

User = get_user_model()


@click.command()
def command():
    """
    For each Library, load the contributors (authors and maintainers) into the
    database.

    Authors are added to the Library as a whole, Maintainers are added to the
    LibraryVersion for that Library and the most recent Version.

    This is intended to be run once to load contributor data into the dev database,
    but its components can be reused (or the command can be changed) to load
    contributor information for prior Boost versions, and on an ongoing basis.

    Idempotent.
    """

    version = Version.objects.most_recent()
    skip_maintainers = False

    for library in Library.objects.all():
        try:
            library_version = LibraryVersion.objects.get(
                version=version, library=library
            )
        except LibraryVersion.DoesNotExist:
            click.secho(
                f"No library version for '{library} and {version}'... skipping maintainers",
                fg="red",
            )
            skip_maintainers = True

        click.secho(f"Getting Library data for '{library.name}'...", fg="green")

        updater = LibraryUpdater()
        libraries_json = updater.get_library_metadata(library.name)

        if isinstance(libraries_json, list):
            # TODO: Fix this once #55 is fixed
            continue

        click.secho(f"Getting authors...", fg="green")
        author_data = libraries_json.get("authors")
        process_author_data(author_data, library)

        if skip_maintainers:
            click.secho(f"... skipping maintainers", fg="red")
            skip_maintainers = False
            continue

        click.secho(f"Getting maintainers...", fg="green")
        maintainer_data = libraries_json.get("maintainers")
        process_maintainer_data(maintainer_data, library_version)

    click.secho("All Done!", fg="green")


def extract_email(val: str) -> str:
    """
    Finds an email address in a string, reformats it, and returns it.
    Assumes the email address is in this format:
    <firstlast -at- domain.com>

    Does not raise errors.

    Includes as many catches for variants in the formatting as I found in a first
    pass.
    """
    result = re.search("<.+>", val)
    if result:
        raw_email = result.group()
        email = (
            raw_email.replace("-at-", "@")
            .replace("- at -", "@")
            .replace("-dot-", ".")
            .replace("<", "")
            .replace(">", "")
            .replace(" ", "")
            .replace("-underscore-", "_")
        )
        try:
            validate_email(email)
        except ValidationError as e:
            logger.info("Could not extract valid email", value=val, exc_msg=str(e))
            return
        return email


def extract_names(val: str) -> list:
    """
    Returns a list of first, last names for the val argument.

    NOTE: This is an overly simplistic solution to importing names.
    Names that don't conform neatly to "First Last" formats will need
    to be cleaned up manually.
    """
    # Strip the email, if present
    email = re.search("<.+>", val)
    if email:
        val = val.replace(email.group(), "")

    return val.strip().rsplit(" ", 1)


def generate_fake_email(val: str) -> str:
    """
    Slugifies a string to make a fake email. Would not necessarily be unique -- this is
    a lazy way for us to avoid creating multiple new user records for one contributor who
    contributes to multiple libraries.
    """
    slug = slugify(val)
    local_email = slug.replace("-", "_")[:50]
    return f"{local_email}@example.com"


def get_contributor_data(contributor: str) -> dict:
    """Takes an author/maintainer string and returns a dict with their data"""
    data = {}

    email = extract_email(contributor)
    if bool(email):
        data["email"] = email
        data["valid_email"] = True
    else:
        data["email"] = generate_fake_email(contributor)
        data["valid_email"] = False

    first_name, last_name = extract_names(contributor)
    data["first_name"], data["last_name"] = first_name[:30], last_name[:30]

    return data


def process_author_data(data: list, obj: Library) -> Library:
    """
    Receives a list of strings from the libraries.json of a Boost library, and
    an object with an "authors" attribute.

    Processes that string into a User object that is added as an
    Author to the Library.
    """
    if not data:
        return obj

    for author in data:
        person_data = get_contributor_data(author)
        user = User.objects.find_user(
            email=person_data["email"].lower(),
            first_name=person_data["first_name"],
            last_name=person_data["last_name"],
        )

        if not user:
            email = person_data.pop("email")
            user = User.objects.create_stub_user(email.lower(), **person_data)
            click.secho(f"---User {user.email} created.", fg="green")

        obj.authors.add(user)
        click.secho(f"---User {user.email} added as an author of {obj}", fg="green")

    return obj


def process_maintainer_data(data: list, obj: LibraryVersion) -> LibraryVersion:
    """
    Receives a list of strings from the libraries.json of a Boost library, and
    an object with a M2M "maintainers" attribute.

    Processes the list of strings into User objects and adds them as Maintainers
    to the object.
    """
    if not data:
        return obj

    for maintainer in data:
        person_data = get_contributor_data(maintainer)
        user = User.objects.find_user(
            email=person_data["email"].lower(),
            first_name=person_data["first_name"],
            last_name=person_data["last_name"],
        )

        if not user:
            email = person_data.pop("email")
            user = User.objects.create_stub_user(email.lower(), **person_data)
            click.secho(f"---User {user.email} created.", fg="green")

        obj.maintainers.add(user)
        click.secho(f"---User {user.email} added as a maintainer of {obj}", fg="green")

    return obj
