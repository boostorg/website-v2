from django.db import migrations
from django.db.models import Exists, OuterRef


def unbind_unverified_claims(apps, schema_editor):
    """Drop commit attribution a member asked for and never confirmed.

    Before the v3 claim flow, asking to claim a commit email bound
    `CommitAuthor.user` at ask time, ahead of the address owner confirming
    anything - so starting a claim and abandoning it was enough to take another
    contributor's commits, and any achievement derived from them.

    Only bindings a person started are cleared. One the email matching in
    `libraries.tasks.update_commit_author_user` would make on its own is left
    alone, and that test is `User.email` because it is what the task itself
    matches on: clearing a binding the next sync re-creates would revoke the
    badges resting on it and re-award them dated today, once per run.

    The claim rows are untouched. An unfinished claim is still a legitimate
    request - it keeps showing in the member's commit-email card and can still
    be completed. Only its premature effect is undone.
    """
    CommitAuthor = apps.get_model("libraries", "CommitAuthor")
    CommitAuthorEmail = apps.get_model("libraries", "CommitAuthorEmail")

    emails = CommitAuthorEmail.objects.filter(author=OuterRef("pk"))
    unbound = list(
        CommitAuthor.objects.filter(user__isnull=False)
        .annotate(
            matches_account_email=Exists(emails.filter(email=OuterRef("user__email"))),
            has_verified_claim=Exists(
                emails.filter(claim_verified=True, claimed_by_id=OuterRef("user_id"))
            ),
            has_abandoned_claim=Exists(
                emails.filter(claim_verified=False, claimed_by_id=OuterRef("user_id"))
            ),
        )
        .filter(
            matches_account_email=False,
            has_verified_claim=False,
            has_abandoned_claim=True,
        )
        .values_list("pk", flat=True)
    )
    CommitAuthor.objects.filter(pk__in=unbound).update(user=None)


class Migration(migrations.Migration):
    dependencies = [
        ("libraries", "0044_merge_20260814_1905"),
    ]

    operations = [
        # Irreversible by intent: the state being left is the wrong one, and
        # which of these bindings a claim had made is exactly what is erased.
        migrations.RunPython(unbind_unverified_claims, migrations.RunPython.noop),
    ]
