import djclick as click

from users.models import User, UserProfileRoutingKey


@click.command()
@click.option(
    "--dry-run",
    is_flag=True,
    help="Report which users would get a new key, without minting any.",
)
def command(dry_run):
    """Mint routing keys for users whose profile URL no longer fits their name.

    Renaming through either profile form mints a key, but the paths outside them
    do not: Django admin, and the display_name a social account overwrites on
    signup. This repairs that drift.

    Safe to re-run. A user whose key still matches their display name is left
    alone, so this only ever appends keys for names that have actually changed.
    Keys are never deleted, so a URL shared before the rename keeps resolving and
    redirects to the new one.
    """
    keys = UserProfileRoutingKey.objects
    users = User.objects.filter(is_active=True).order_by("pk")
    total = users.count()

    stale = []
    for user in users.iterator():
        current = keys.current_for(user)
        if not keys.matches_display_name(current, user):
            stale.append((user, current))

    counted = f"{total} user{'' if total == 1 else 's'}"
    if not stale:
        click.secho(f"Checked {counted}; every key is current.", fg="green")
        return

    for user, current in stale:
        previous = current.routing_key if current else "(none)"
        if dry_run:
            click.echo(f"  {user.pk}: {previous} -> {keys.expected_base(user)}-????")
        else:
            click.echo(f"  {user.pk}: {previous} -> {keys.mint_for(user).routing_key}")

    verb = "would be minted" if dry_run else "minted"
    click.secho(f"{len(stale)} of {counted}: key {verb}.", fg="blue")
