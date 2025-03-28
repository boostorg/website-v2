# Generated by Django 4.2.16 on 2024-12-18 18:25
from datetime import timedelta

from django.conf import settings
from django.db import migrations
from django.db.models import Q
from django.utils import timezone


def schedule_stub_users_for_deletion(apps, schema_editor):
    User = apps.get_model("users", "User")
    delete_after = timezone.now() + timedelta(
        days=settings.ACCOUNT_DELETION_GRACE_PERIOD_DAYS
    )
    print(f"\nScheduling stub users for deletion on {delete_after:%m/%d/%Y}")
    updated = User.objects.filter(email__endswith="@example.com", claimed=False).filter(
        Q(submitted_reviews__isnull=False) | Q(managed_reviews__isnull=False)
    ).update(delete_permanently_at=delete_after)
    print(f"Scheduled {updated} users for deletion...", end="")


class Migration(migrations.Migration):

    dependencies = [
        ("versions", "0014_version_sponsor_message"),
        ("users", "0015_user_delete_permanently_at"),
    ]

    operations = [
        migrations.RunPython(
            schedule_stub_users_for_deletion,
            migrations.RunPython.noop,  # Not feasible to re-populate these users
        ),
    ]
