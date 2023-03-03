import djclick as click
import random
import re
import structlog

from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.text import slugify
from faker import Faker

from libraries import utils
from libraries.github import LibraryUpdater
from libraries.models import Library, LibraryVersion
from versions.models import Version

fake = Faker()

logger = structlog.get_logger()

User = get_user_model()


@click.command()
def command():
    """
    Idempotent.

    Get all the libraries.

    For each library:
    - Retrieve and extract info about their authors and maintainers
    - Use that info to create or update User records
    - Associate the User records for those authors and maintainers to the
      Library

    - [x] Retrieve their GH record
    - [x] Get the file with the data in it and parse it
    - [x] Extract author and maintainer data
    - [x] Method to extract email
    - [x] Method to extract first and last
    - [x] If no email, method to create fake email
    - [x] Add a User model field to denote a fake email
    - [x] Add a User model field to denote unclaimed user
    - [x] Method to get or create new user with email
    - [x] If created, mark as Unclaimed
    - [x] If fake email, mark fake email
    - [x] Add the authors as Authors to the Library

    # Dealing with maintainers
    - [x] Remove 'maintainers' from Library and add to LibraryVersion
    - [x] Retrieve most recent LibraryVersion
    - [x] Add maintainers to the most recent LibraryVersion

    NEW ISSUES
    - [ ] Process to claim your user with your email
    - [ ] Add process to update authors to the library syncing
    - [ ] Add process to update maintainers to the LibraryVersion syncing
    """

    library = Library.objects.order_by("?").first()
    version = Version.objects.most_recent()
    click.secho(f"Getting Library data for '{library.name}'...", fg="green")

    updater = LibraryUpdater()
    result = updater.get_library_metadata(library.name)

    if type(result) is list:
        breakpoint()
        # TODO: See line 211 in github.py
        raise

    authors = result.get("authors")
    maintainers = result.get("maintainers")

    click.secho(f"Getting authors...", fg="green")
    for a in authors:
        person_data = get_person_data(a)
        user, created = User.objects.get_or_create(
            email=person_data["email"],
            defaults={
                "first_name": person_data["first_name"][:30],
                "last_name": person_data["last_name"][:30],
            },
        )
        click.secho(f"User {user.email} saved. Created? {created}", fg="green")

        if created:
            user.claimed = False
            user.is_active = False
            user.save()

        library.authors.add(user)
        click.secho(
            f"User {user.email} added as a maintainer of {library.name}", fg="green"
        )

    if maintainers:
        try:
            library_version = LibraryVersion.objects.get(
                library=library, version=version
            )
        except LibraryVersion.DoesNotExist:
            logger.info("No library version", version=version.pk, library=library.pk)
            return

        click.secho(f"Getting maintainers...", fg="green")
        for m in maintainers:
            person_data = get_person_data(m)

            user, created = User.objects.get_or_create(
                email=person_data["email"],
                defaults={
                    "first_name": person_data["first_name"][:30],
                    "last_name": person_data["last_name"][:30],
                },
            )
            click.secho(f"--User {user.email} saved. Created? {created}", fg="green")

            if created:
                user.claimed = False
                user.is_active = False
                user.valid_email = person_data["valid_email"]
                user.save()

            library_version.maintainers.add(user)
            click.secho(
                f"--User {user.email} added as a maintainer of {library.name}",
                fg="green",
            )

    click.secho("All done!", fg="green")


def get_person_data(person: str) -> dict:
    """Takes an author/maintainer string and returns a dict with their data"""
    person_data = {}
    person_data["meta"] = person
    person_data["valid_email"] = False

    names = utils.get_names(person)
    person_data["first_name"] = names[0]
    person_data["last_name"] = names[1]

    email = utils.extract_email(person)
    if email:
        person_data["email"] = email
        person_data["valid_email"] = True
    else:
        person_data["email"] = utils.generate_email(
            f"{person_data['first_name']} {person_data['last_name']}"
        )

    return person_data
