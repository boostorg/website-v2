# Generated by Django 4.2.16 on 2025-01-21 01:15

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("versions", "0017_alter_review_review_manager_alter_review_submitters"),
    ]

    operations = [
        migrations.AddField(
            model_name="version",
            name="financial_committee_members",
            field=models.ManyToManyField(
                blank=True,
                help_text="Financial Committee members who are responsible for this release.",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
