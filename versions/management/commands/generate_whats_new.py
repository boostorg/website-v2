import djclick as click

from core.models import RenderedContent
from versions.tasks import (
    WHATS_NEW_SYSTEM_PROMPT,
    _release_note_text,
    dispatch_whats_new,
    generate_whats_new,
)
from versions.models import Version


@click.command()
@click.option(
    "--all-missing",
    is_flag=True,
    default=False,
    help=(
        "Queue generation for every active version that has stored release "
        "notes in the Rendered Content page, but no summary yet. Versions "
        "without release notes are skipped."
    ),
)
@click.option(
    "--version",
    "version_slug",
    default=None,
    help="Slug of a single version to (re)generate.",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Regenerate even when a summary already exists.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="List the versions that would be queued without queuing them.",
)
@click.option(
    "--validate",
    is_flag=True,
    default=False,
    help=(
        "Run the prompt synchronously against --limit recent versions and print "
        "the LLM output for human review. No DB writes."
    ),
)
@click.option(
    "--limit",
    default=10,
    type=int,
    help="Number of versions to process when --validate is set.",
)
def command(
    all_missing: bool,
    version_slug: str | None,
    force: bool,
    dry_run: bool,
    validate: bool,
    limit: int,
):
    """Generate AI What's New summaries for Boost releases."""
    if validate:
        _validate(limit)
        return

    if not all_missing and not version_slug:
        raise click.UsageError("Pass --all-missing, --version <slug>, or --validate.")

    versions, reason = _select_versions(version_slug, force)
    if not versions:
        _warn_no_versions(reason, version_slug)
        return

    for version in versions:
        if dry_run:
            click.secho(
                f"[dry-run] would queue whats_new generation for {version.name}",
                fg="cyan",
            )
            continue
        click.secho(f"queueing whats_new for {version.name}", fg="green")
        dispatch_whats_new(version.pk)


def _select_versions(version_slug: str | None, force: bool):
    """Return ``(versions, reason)`` where ``reason`` explains an empty list.

    ``reason`` is ``None`` when ``versions`` is non-empty. Otherwise it is one of
    ``"slug_not_found"``, ``"already_populated"``, ``"none_missing"``, or
    ``"no_release_notes"`` — see ``_warn_no_versions`` for the user-facing text.
    """
    qs = Version.objects.active().exclude(name__in=["master", "develop"])
    if version_slug:
        qs = qs.filter(slug=version_slug)
        if not qs.exists():
            return [], "slug_not_found"
    if not force:
        filtered = qs.filter(whats_new="")
        if not filtered.exists():
            return [], "already_populated" if version_slug else "none_missing"
        qs = filtered

    rendered_keys = set(
        RenderedContent.objects.filter(
            cache_key__startswith="release_notes_boost-"
        ).values_list("cache_key", flat=True)
    )
    versions = [
        v for v in qs.order_by("name") if v.release_notes_cache_key in rendered_keys
    ]
    if versions:
        return versions, None
    return [], "no_release_notes"


def _warn_no_versions(reason: str | None, version_slug: str | None) -> None:
    if reason == "slug_not_found":
        message = (
            f"No active version with slug '{version_slug}'. "
            "Check the slug format (e.g. boost-1-90-0)."
        )
    elif reason == "already_populated":
        message = (
            f"Version '{version_slug}' already has a whats_new summary. "
            "Pass --force to regenerate."
        )
    elif reason == "none_missing":
        message = (
            "All active versions already have whats_new summaries. "
            "Use --version <slug> --force to regenerate one."
        )
    elif version_slug:
        message = (
            f"Version '{version_slug}' has no stored release notes. "
            "Run `manage.py import_release_notes` first."
        )
    else:
        message = (
            "No versions with stored release notes to process. "
            "Run `manage.py import_release_notes` first."
        )
    click.secho(message, fg="yellow")


def _validate(limit: int):
    """Run the prompt against the latest `limit` versions that have release
    notes and print results.

    Used to satisfy the acceptance criterion that the prompt is reviewed against
    >=10 past Boost release notes before sign-off. Bypasses the save chain so
    nothing is written to the database.
    """
    rendered_keys = set(
        RenderedContent.objects.filter(
            cache_key__startswith="release_notes_boost-"
        ).values_list("cache_key", flat=True)
    )
    candidates = (
        Version.objects.active()
        .exclude(name__in=["master", "develop"])
        .order_by("-name")
    )
    versions = []
    for version in candidates:
        if version.release_notes_cache_key in rendered_keys:
            versions.append(version)
            if len(versions) >= limit:
                break

    click.secho(
        f"Validating What's New prompt against {len(versions)} version(s) "
        f"(requested up to {limit}).\n",
        fg="green",
    )
    click.secho(f"--- system prompt ---\n{WHATS_NEW_SYSTEM_PROMPT}\n", fg="white")

    if not versions:
        click.secho(
            "No versions with stored release notes found. "
            "Run `manage.py import_release_notes --new=False` first.",
            fg="yellow",
        )
        return

    for version in versions:
        click.secho(f"\n=== {version.name} ===", fg="cyan")
        rendered_content = RenderedContent.objects.get(
            cache_key=version.release_notes_cache_key
        )
        input_chars = len(_release_note_text(rendered_content))
        click.echo(f"input_chars={input_chars}")
        result = generate_whats_new.run(version.pk)
        click.echo(result or "<no output>")
