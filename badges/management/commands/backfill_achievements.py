"""Backfill automatic achievements from existing Boost data.

Walks each wired source and creates the grants it yields that the database is
missing, then recalculates badges once per affected (user, achievement) pair.

**Additive only.** This is ``services.sync_source`` with ``remove=False``, so it
can never undo an attribution, which is what makes it safe for the weekly
pipeline to run unattended. To remove the grants a source has stopped supporting,
use ``reconcile_achievements``.
"""

from django.core.management.base import BaseCommand, CommandError

from badges import sources
from badges.management.arguments import (
    add_sync_log_arguments,
    positive_integer,
    resolve_sync_log,
)
from badges.models import Achievement
from badges.services import SYNC_BATCH_SIZE, recalculate_badges, sync_source


class Command(BaseCommand):
    """Create automatic UserAchievement rows from historical data."""

    help = "Backfill automatic achievements from existing data."

    def add_arguments(self, parser):
        """Register CLI options."""
        parser.add_argument(
            "--source",
            dest="slugs",
            action="append",
            choices=sources.AUTOMATIC_SLUGS,
            help="Backfill only this source slug; repeat for several (default: all).",
        )
        parser.add_argument(
            "--batch-size",
            type=positive_integer,
            default=SYNC_BATCH_SIZE,
            help=f"Rows per bulk_create batch (default: {SYNC_BATCH_SIZE}).",
        )
        add_sync_log_arguments(parser)

    def handle(self, *args, **options):
        """Run the backfill for the requested source(s)."""
        explicit = bool(options["slugs"])
        slugs = options["slugs"] or sources.AUTOMATIC_SLUGS
        batch_size = options["batch_size"]
        trigger, actor = resolve_sync_log(options, self.stderr)

        achievements = {
            achievement.slug: achievement
            for achievement in Achievement.objects.filter(slug__in=slugs)
        }
        missing = sorted(set(slugs) - set(achievements))
        if missing:
            # A named source that is missing is a deploy bug, so fail on it. A
            # scheduled sweep instead reports it and keeps going: one unseeded
            # slug must not cost the other five sources their backfill.
            if explicit:
                raise CommandError(
                    "No Achievement row for wired source(s): "
                    f"{', '.join(missing)}. Run migrations to seed the catalogue."
                )
            self.stderr.write(
                "Skipping wired source(s) with no Achievement row: "
                f"{', '.join(missing)}. Run migrations to seed the catalogue."
            )
            unseeded = set(missing)
            slugs = [slug for slug in slugs if slug not in unseeded]
            if not slugs:
                raise CommandError("No wired source has an Achievement row.")

        dirty_pairs = set()
        for slug in slugs:
            achievement = achievements[slug]
            result = sync_source(
                slug,
                achievement,
                remove=False,
                batch_size=batch_size,
                trigger=trigger,
                actor=actor,
            )
            # Only the members who actually gained a row, so a repeat run - the
            # weekly one - does not recalculate every pair in the system.
            # ``outstanding`` is every one of them here, this run being additive,
            # but reading it from the result means no caller has to know that.
            dirty_pairs.update(
                (user_id, achievement.pk) for user_id in result.outstanding()
            )
            # ``describe()`` rather than a line of its own, so this and the
            # reconcile command and the admin's preview cannot reach different
            # conclusions about the same numbers. It can never report a removal
            # here: ``remove=False`` leaves the stale set empty.
            self.stdout.write(f"  {result.slug}: {result.describe()}")

        for user_id, achievement_id in dirty_pairs:
            recalculate_badges(user_id, achievement_id)
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Recalculated {len(dirty_pairs)} (user, achievement) pair(s)."
            )
        )
