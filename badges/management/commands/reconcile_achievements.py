"""Make automatic achievements agree with the sources they came from.

Two-way, unlike ``backfill_achievements``, which only ever adds. One walk of each
source creates the grants it yields that are missing and deletes the stored grants
it no longer yields - a commit re-assigned to another author, a maintainer dropped
from a library, a news entry unpublished. Manual grants are never touched, and
badges follow in both directions: a tier below its threshold is cascade-revoked, and
one back above it is re-earned.

Scope it and rehearse it: ``--dry-run`` reports without writing, ``--user`` and
``--source`` keep the blast radius to what you meant to fix, and ``--remove-only``
leaves the additive half out when removal is all you want.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from badges import sources
from badges.management.arguments import (
    add_sync_log_arguments,
    positive_integer,
    resolve_sync_log,
)
from badges.models import Achievement
from badges.services import SYNC_BATCH_SIZE, recalculate_badges, sync_source

User = get_user_model()


class Command(BaseCommand):
    """Sync automatic UserAchievement rows against the sources they derive from."""

    help = "Add and remove automatic achievements so they match their sources."

    def add_arguments(self, parser):
        """Register CLI options."""
        parser.add_argument(
            "--source",
            dest="slugs",
            action="append",
            choices=sources.AUTOMATIC_SLUGS,
            help="Reconcile only this source slug; repeat for several (default: all).",
        )
        parser.add_argument(
            "--user",
            dest="users",
            action="append",
            metavar="EMAIL_OR_ID",
            help=(
                "Restrict the run to this member, by email or primary key; "
                "repeat for several (default: every member)."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change and write nothing.",
        )
        parser.add_argument(
            "--remove-only",
            action="store_true",
            help=(
                "Delete stale grants without creating missing ones, which is what "
                "this command did before it was two-way."
            ),
        )
        parser.add_argument(
            "--allow-empty",
            action="store_true",
            help=(
                "Delete even when a source yields no rows at all. Without this, an "
                "empty source is treated as broken rather than as evidence that "
                "every grant it feeds is stale."
            ),
        )
        parser.add_argument(
            "--batch-size",
            type=positive_integer,
            default=SYNC_BATCH_SIZE,
            help=f"Rows per insert and delete batch (default: {SYNC_BATCH_SIZE}).",
        )
        add_sync_log_arguments(parser)

    def handle(self, *args, **options):
        """Sync the requested source(s) and report what changed."""
        dry_run = options["dry_run"]
        slugs = options["slugs"] or sources.AUTOMATIC_SLUGS
        user_ids = self._resolve_users(options["users"])
        trigger, actor = resolve_sync_log(options, self.stderr)

        achievements = {
            achievement.slug: achievement
            for achievement in Achievement.objects.filter(slug__in=slugs)
        }
        missing = sorted(set(slugs) - set(achievements))
        if missing:
            # Unlike the backfill, an unseeded slug is never merely skipped: it
            # has no stored grants either, so there is nothing to reconcile and
            # nothing to lose by insisting the catalogue is intact first.
            raise CommandError(
                "No Achievement row for wired source(s): "
                f"{', '.join(missing)}. Run migrations to seed the catalogue."
            )

        if dry_run:
            self.stdout.write("Dry run: nothing will be written.")

        results = [
            sync_source(
                slug,
                achievements[slug],
                user_ids=user_ids,
                add=not options["remove_only"],
                dry_run=dry_run,
                allow_empty=options["allow_empty"],
                batch_size=options["batch_size"],
                trigger=trigger,
                actor=actor,
            )
            for slug in slugs
        ]

        dirty_pairs = set()
        for result in results:
            self.stdout.write(f"  {result.slug}: {result.describe()}")
            dirty_pairs.update(
                (user_id, achievements[result.slug].pk) for user_id in result.changed
            )

        if not dry_run:
            # Removals already recalculated themselves through ``post_delete``;
            # additions did not, and a second pass over a pair is idempotent.
            for user_id, achievement_id in dirty_pairs:
                recalculate_badges(user_id, achievement_id)

        added = sum(result.added for result in results)
        removed = sum(result.removed for result in results if not result.refused)
        lead = "Would add" if dry_run else "Added"
        tail = "remove" if dry_run else "removed"
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {lead} {added} and {tail} {removed} grant(s) across "
                f"{len(dirty_pairs)} (user, achievement) pair(s)."
            )
        )
        refused = [result.slug for result in results if result.refused]
        if refused:
            # Loud, and on stderr: a refusal means a source read empty, which is
            # a data problem outliving this command.
            self.stderr.write(
                "Refused to remove anything for: "
                f"{', '.join(refused)}. The source(s) yielded nothing while grants "
                "exist. Investigate the source, or pass --allow-empty if the "
                "emptiness is real."
            )

    def _resolve_users(self, identifiers):
        """Turn ``--user`` values into primary keys, or fail listing the strays.

        Accepts an email or a primary key because both are how a member gets
        named in practice - an email from a bug report, an id from an admin URL.
        """
        if not identifiers:
            return None

        user_ids = set()
        unknown = []
        for identifier in identifiers:
            lookup = (
                {"pk": int(identifier)}
                if identifier.isdigit()
                else {"email__iexact": identifier}
            )
            pk = User.objects.filter(**lookup).values_list("pk", flat=True).first()
            if pk is None:
                unknown.append(identifier)
            else:
                user_ids.add(pk)

        if unknown:
            raise CommandError(f"No such member(s): {', '.join(unknown)}.")
        return user_ids
