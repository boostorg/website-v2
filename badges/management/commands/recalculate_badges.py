"""Rebuild UserBadge state from scratch.

Visits every (user, achievement) pair with an achievement row *or* a badge row.
Useful after editing thresholds, fixing data, or changing the recalculation rules.
Idempotent.
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
