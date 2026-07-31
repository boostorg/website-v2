"""Seed the canonical achievement types, badges, and tier thresholds.

Delegates to ``badges.catalogue.seed_catalogue``, which the test suite also
seeds through because pytest runs with ``--no-migrations``. Idempotent; only
sets thresholds on first creation, so admin tuning is never overwritten.

Editing ``badges.catalogue`` therefore changes what a *fresh* run of this
migration produces. Already-seeded databases keep their existing values, so a
threshold change needs its own follow-up data migration - see the module
docstring in ``badges/catalogue.py``.
"""

from django.db import migrations

from badges.catalogue import seed_catalogue


def seed(apps, schema_editor):
    """Seed the catalogue using historical models."""
    seed_catalogue(
        apps.get_model("badges", "Achievement"),
        apps.get_model("badges", "Badge"),
        apps.get_model("badges", "BadgeTier"),
    )


class Migration(migrations.Migration):
    """Data migration seeding the achievement/badge catalogue."""

    dependencies = [
        ("badges", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
