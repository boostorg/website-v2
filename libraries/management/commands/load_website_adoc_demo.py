from pathlib import Path

import djclick as click
from django.urls import reverse

from libraries.models import Library, LibraryVersion
from libraries.website_adoc import website_adoc_fields
from versions.models import Version

DEFAULT_DEMO_FILE = Path(__file__).resolve().parents[2] / "website_adoc_demo.adoc"


@click.command()
@click.option(
    "--library",
    "library_slug",
    required=True,
    help="Library slug to load the demo onto (e.g. 'beast').",
)
@click.option(
    "--version",
    "version_slug",
    default=None,
    help="Boost version slug (e.g. '1.90.0'). Defaults to the most recent.",
)
@click.option(
    "--file",
    "file_path",
    default=str(DEFAULT_DEMO_FILE),
    help="Path to a website.adoc file (defaults to the bundled demo).",
)
@click.option(
    "--clear",
    is_flag=True,
    default=False,
    help="Clear website_adoc on the target instead of loading.",
)
def command(library_slug, version_slug, file_path, clear):
    """Load a demo meta/website.adoc onto a library version so the subpage can be
    inspected in a browser.

    Dev/QA helper: parses through the exact same build_website_adoc() path as
    ingestion and stores the result on LibraryVersion.website_adoc, so the real
    view + template render it. Use --clear to restore the empty state.
    """
    try:
        library = Library.objects.get(slug=library_slug)
    except Library.DoesNotExist:
        raise click.ClickException(f"No library with slug '{library_slug}'.")

    version = (
        Version.objects.filter(slug=version_slug).first()
        if version_slug
        else Version.objects.most_recent()
    )
    if not version:
        raise click.ClickException(f"No version matching '{version_slug}'.")

    try:
        library_version = LibraryVersion.objects.get(library=library, version=version)
    except LibraryVersion.DoesNotExist:
        raise click.ClickException(
            f"'{library_slug}' has no LibraryVersion for {version.slug}."
        )

    if clear:
        LibraryVersion.objects.filter(pk=library_version.pk).update(
            website_adoc_source=None, website_adoc=None
        )
        click.secho(
            f"Cleared website_adoc on {library_slug} ({version.slug}).", fg="yellow"
        )
        return

    path = Path(file_path)
    if not path.exists():
        raise click.ClickException(f"File not found: {file_path}")

    fields = website_adoc_fields(path.read_bytes())
    parsed = fields["website_adoc"]
    if not parsed:
        raise click.ClickException(
            f"{file_path} parsed to nothing (empty or placeholder-only)."
        )

    LibraryVersion.objects.filter(pk=library_version.pk).update(**fields)
    click.secho(f"Loaded {path.name} onto {library_slug} ({version.slug}).", fg="green")
    click.echo("Sections: " + ", ".join(sorted(parsed.keys())))
    url = reverse(
        "library-detail",
        kwargs={"version_slug": version.slug, "library_slug": library_slug},
    )
    click.echo(f"View it at: {url}")
