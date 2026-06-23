import djclick as click

from core.models import RenderedContent
from versions.models import Version
from versions.releases import get_release_notes_for_version


@click.command()
def command():
    """Seed release-notes RenderedContent for every Version in the local DB.

    Uses the same source-of-truth strategy as prod
    (`get_release_notes_for_version`): S3 first (asciidoc, for 1.90.0 onwards),
    falling back to the boostorg/website GitHub history page (html) for older
    versions. Upserts a `RenderedContent` row keyed by
    `version.release_notes_cache_key`.
    """
    seeded, skipped, failed = [], [], []

    for version in Version.objects.all().order_by("name"):
        if not version.cleaned_version_parts:
            skipped.append((version.name, "no version number"))
            continue

        try:
            content, processed_content, content_type = get_release_notes_for_version(
                version.pk
            )
        except Exception as exc:
            failed.append((version.name, str(exc)))
            continue

        if not content:
            skipped.append((version.name, "no release notes found"))
            continue

        RenderedContent.objects.update_or_create(
            cache_key=version.release_notes_cache_key,
            defaults={
                "content_type": content_type,
                "content_original": content,
                "content_html": processed_content,
            },
        )
        seeded.append(version.name)

    click.secho(f"Seeded: {len(seeded)}", fg="green")
    for name in seeded:
        click.echo(f"  ok    {name}")
    click.secho(f"Skipped: {len(skipped)}", fg="yellow")
    for name, reason in skipped:
        click.echo(f"  skip  {name} ({reason})")
    click.secho(f"Failed: {len(failed)}", fg="red")
    for name, reason in failed:
        click.echo(f"  fail  {name} ({reason})")
