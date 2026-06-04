import djclick as click

from django.db import transaction

from core.services.popular_search_terms import (
    refresh_popular_search_terms as _refresh_service,
)
from core.tasks import refresh_popular_search_terms as _refresh_task


@click.command()
@click.option(
    "--queue",
    is_flag=True,
    default=False,
    help=(
        "Dispatch the refresh to Celery (matches the admin 'Refresh from "
        "Algolia' button and the weekly cron). Default is to run inline so "
        "you see the result immediately."
    ),
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help=(
        "Fetch from Algolia and run the LLM filter, but roll back any DB "
        "writes. Useful for previewing what the next refresh would do. "
        "Incompatible with --queue."
    ),
)
def command(queue: bool, dry_run: bool):
    """Refresh PopularSearchTerm rows from Algolia, via the same service the
    weekly Celery task uses."""
    if queue and dry_run:
        raise click.UsageError("--queue and --dry-run are mutually exclusive.")

    if queue:
        async_result = _refresh_task.delay()
        click.secho(
            f"Queued refresh_popular_search_terms (task id: {async_result.id})",
            fg="green",
        )
        return

    if dry_run:
        click.secho(
            "[dry-run] running refresh; DB writes will be rolled back", fg="cyan"
        )
        with transaction.atomic():
            result = _refresh_service()
            transaction.set_rollback(True)
    else:
        result = _refresh_service()

    _print_result(result, dry_run=dry_run)


def _print_result(result: dict, *, dry_run: bool) -> None:
    if result.get("skipped"):
        click.secho(
            "Refresh skipped — no DB writes (likely no recent Version or "
            "empty Algolia response). See result below.",
            fg="yellow",
        )
    prefix = "[dry-run] " if dry_run else ""
    click.secho(
        f"{prefix}ai_kept={result['ai_kept']} "
        f"new={result['new']} updated={result['updated']} "
        f"demoted={result['demoted']} skipped={result['skipped']}",
        fg="green",
    )
