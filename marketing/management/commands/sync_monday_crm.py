import logging

import djclick as click
from django.contrib.auth import get_user_model

from marketing.models import CapturedEmail
from marketing.monday import MondayClient

User = get_user_model()
logger = logging.getLogger(__name__)


@click.command()
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Print what would be synced without making API calls.",
)
@click.option(
    "--board",
    type=click.Choice(["contacts", "leads", "all"]),
    default="all",
    show_default=True,
    help="Which Monday.com board to sync.",
)
def command(dry_run, board):
    """Sync Users and CapturedEmails to Monday.com CRM boards.

    contacts: active + claimed Users  -> Contacts board
    leads:    non-opted-out emails    -> Leads board
    all:      both boards (default)
    """
    if dry_run:
        click.secho("DRY RUN — no data will be sent to Monday.com", fg="yellow")

    client = None if dry_run else MondayClient()

    if board in ("contacts", "all"):
        _sync_contacts(client, dry_run)

    if board in ("leads", "all"):
        _sync_leads(client, dry_run)


def _sync_contacts(client, dry_run):
    users = User.objects.filter(is_active=True, claimed=True).order_by("pk")
    total = users.count()
    click.secho(f"Syncing {total} contacts to Monday.com Contacts board...", fg="green")

    if dry_run:
        for user in users.iterator():
            click.echo(f"  [DRY RUN] contact: {user.email}")
        return

    created, updated = client.bulk_upsert_contacts(users)
    click.secho(
        f"Contacts done: {created} created, {updated} updated.",
        fg="green",
    )


def _sync_leads(client, dry_run):
    leads = (
        CapturedEmail.objects.filter(opted_out=False)
        .select_related("page")
        .order_by("pk")
    )
    total = leads.count()
    click.secho(f"Syncing {total} leads to Monday.com Leads board...", fg="green")

    if dry_run:
        for lead in leads.iterator():
            click.echo(f"  [DRY RUN] lead: {lead.email}")
        return

    created, updated = client.bulk_upsert_leads(leads)
    click.secho(
        f"Leads done: {created} created, {updated} updated.",
        fg="green",
    )
