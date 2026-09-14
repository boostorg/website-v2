import djclick as click

from django.contrib.auth import get_user_model
from django.db import models
from django.conf import settings

from mailing_list.models import MailingListActivity, ListPosting


@click.command()
@click.option(
    "--dry",
    is_flag=True,
    help="Returns the number of users who's activity would be updated without changing them.",
)
@click.option(
    "--user-id",
    is_flag=False,
    help="Optional User id. If passed, will only update the activity of the specified user.",
)
def command(dry, user_id):
    if not settings.HYPERKITTY_DATABASE_NAME:
        click.echo("HYPERKITTY_DATABASE_NAME setting is empty. Not syncing.")
        return

    click.echo("Beginning Mailing List Activity update...")

    User = get_user_model()
    qs = User.objects.none()
    if user_id:
        qs = User.objects.filter(id=user_id)
    else:
        qs = User.objects.all()
    qs = (
        qs.filter(is_active=True)
        .prefetch_related("commitauthor_set__commitauthoremail_set")
        .annotate(commit_author_count=models.Count("commitauthor"))
        .filter(commit_author_count__gt=0)
    )

    click.echo(f"{qs.count()} users found to update. Beginning activty count...")
    mla_list = []
    count = 0
    for u in qs:
        count += 1
        if count % 50 == 0:
            click.echo(f"{count} users processed.")
        if dry:
            try:
                mla = MailingListActivity.objects.get(user=u)
            except MailingListActivity.DoesNotExist:
                click.echo(f"No activity for {u} exists, skipping...")
                continue
        mla, _ = MailingListActivity.objects.get_or_create(
            user=u, defaults={"count": 0}
        )

        emails = [
            x.email
            for x in u.commitauthor_set.annotate(
                email=models.F("commitauthoremail__email")
            )
        ]
        postings_count = ListPosting.objects.filter(sender_id__in=emails).count()
        if dry:
            if mla.count != postings_count:
                click.echo(f"{u} would be updated from {mla.count} to {postings_count}")
            continue

        mla.count = postings_count
        mla_list.append(mla)

    if not dry:
        MailingListActivity.objects.bulk_update(mla_list, ["count"])

    click.echo("Update complete.")
