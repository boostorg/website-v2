"""Rebuild UserBadge state from scratch.

Recalculates every (user, achievement) pair that has an achievement row *or* a
badge row - see ``badges.services.achievement_pairs`` for why both halves are
needed.

Useful after editing thresholds, fixing data, or a code change to the
recalculation rules. Idempotent.
"""

from django.core.management.base import BaseCommand

from badges.services import achievement_pairs, recalculate_many


class Command(BaseCommand):
    """Recalculate badges for every user with achievements or badges."""

    help = "Recalculate UserBadge state for every (user, achievement) pair."

    def handle(self, *args, **options):
        """Recalculate each distinct (user, achievement) pair worth visiting."""
        count = recalculate_many(achievement_pairs())
        self.stdout.write(
            self.style.SUCCESS(f"Recalculated {count} (user, achievement) pair(s).")
        )
