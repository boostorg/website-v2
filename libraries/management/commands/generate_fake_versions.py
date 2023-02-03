import djclick as click
import random

from datetime import timedelta
from django.utils import timezone
from faker import Faker

from libraries.models import Library, LibraryVersion
from versions.models import Version

fake = Faker()


@click.command()
def command():
    """
    Create Version objects and attach libraries to them.
    """

    # Create versions
    release_date = timezone.now() - timedelta(days=3650)
    for i in range(30, 80):
        version, created = Version.objects.get_or_create(
            name=f"1.{i}.0",
            defaults={
                "release_date": release_date,
                "description": fake.paragraph(nb_sentences=2),
                "active": True,
            },
        )
        if created:
            click.secho(f"Version {version.name} created succcessfully", fg="green")
        else:
            click.secho(f"Version {version.name} already exists.")

        delta = random.choice(range(20, 50))
        release_date += timedelta(delta)

    for library in Library.objects.all():
        # Select the starting version randomly
        start_version = Version.objects.order_by("?").first()

        # Add a LibraryVersion for each Version newer than the starting version
        for version in Version.objects.filter(
            release_date__gt=start_version.release_date
        ):
            lib_version, created = LibraryVersion.objects.get_or_create(
                library=library, version=version
            )
            if created:
                click.secho(f"---{lib_version} created succcessfully", fg="green")
            else:
                click.secho(f"LibraryVersion {lib_version} already exists.")

    click.secho("All done!", fg="green")
