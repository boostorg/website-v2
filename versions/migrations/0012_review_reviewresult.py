# Generated by Django 4.2.16 on 2024-11-13 16:12

from django.conf import settings
from django.contrib.postgres.operations import UnaccentExtension
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("versions", "0011_version_full_release"),
    ]

    operations = [
        UnaccentExtension(),
        migrations.CreateModel(
            name="Review",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("submission", models.CharField()),
                ("submitter_raw", models.CharField()),
                ("review_manager_raw", models.CharField(blank=True, default="Needed!")),
                ("review_dates", models.CharField()),
                ("github_link", models.URLField(blank=True, default="")),
                ("documentation_link", models.URLField(blank=True, default="")),
                (
                    "review_manager",
                    models.ForeignKey(
                        default=None,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="managed_reviews",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "submitters",
                    models.ManyToManyField(
                        related_name="submitted_reviews", to=settings.AUTH_USER_MODEL
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ReviewResult",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("short_description", models.CharField()),
                ("is_most_recent", models.BooleanField(default=True)),
                ("announcement_link", models.URLField(blank=True, default="")),
                (
                    "review",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="results",
                        to="versions.review",
                    ),
                ),
            ],
            options={
                "verbose_name_plural": "review results",
            },
        ),
    ]
