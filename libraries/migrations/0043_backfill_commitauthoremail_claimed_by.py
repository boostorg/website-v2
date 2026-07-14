from django.db import migrations
from django.db.models import OuterRef, Subquery


def backfill_claimed_by(apps, schema_editor):
    """Historically a claim was recorded by binding author.user at ask time,
    so for every row that has a claim token and a bound author, that user is
    the best available signal of who asked. Covers verified claims and open
    pending ones. Rows bound only by the email/github matching heuristics
    have no claim_hash and are deliberately left alone.
    """
    CommitAuthorEmail = apps.get_model("libraries", "CommitAuthorEmail")
    CommitAuthor = apps.get_model("libraries", "CommitAuthor")
    CommitAuthorEmail.objects.filter(
        author__user__isnull=False, claim_hash__isnull=False
    ).update(
        claimed_by_id=Subquery(
            CommitAuthor.objects.filter(pk=OuterRef("author_id")).values("user_id")[:1]
        )
    )


class Migration(migrations.Migration):
    dependencies = [
        ("libraries", "0042_commitauthoremail_claimed_by"),
    ]

    operations = [
        migrations.RunPython(backfill_claimed_by, migrations.RunPython.noop),
    ]
