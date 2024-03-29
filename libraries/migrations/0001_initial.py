# Generated by Django 3.2.2 on 2022-07-17 16:13

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("versions", "0005_version_active"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Category",
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
                ("name", models.CharField(max_length=100)),
            ],
        ),
        migrations.CreateModel(
            name="Library",
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
                ("name", models.CharField(db_index=True, max_length=100)),
                ("description", models.TextField(blank=True, null=True)),
                ("github_url", models.URLField(blank=True, max_length=500, null=True)),
                (
                    "cpp_standard_minimum",
                    models.CharField(blank=True, max_length=50, null=True),
                ),
                (
                    "active_development",
                    models.BooleanField(db_index=True, default=True),
                ),
                (
                    "last_github_update",
                    models.DateTimeField(blank=True, db_index=True, null=True),
                ),
                ("closed_prs_per_month", models.IntegerField(blank=True, null=True)),
                ("open_issues", models.IntegerField(blank=True, null=True)),
                ("commits_per_release", models.IntegerField(blank=True, null=True)),
                (
                    "authors",
                    models.ManyToManyField(
                        related_name="authors", to=settings.AUTH_USER_MODEL
                    ),
                ),
                (
                    "categories",
                    models.ManyToManyField(
                        related_name="libraries", to="libraries.Category"
                    ),
                ),
                (
                    "first_release",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="first_releases",
                        to="versions.version",
                    ),
                ),
                (
                    "maintainers",
                    models.ManyToManyField(
                        related_name="maintainers", to=settings.AUTH_USER_MODEL
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="PullRequest",
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
                ("title", models.CharField(max_length=255)),
                ("number", models.IntegerField()),
                ("github_id", models.CharField(db_index=True, max_length=100)),
                ("is_open", models.BooleanField(db_index=True, default=False)),
                ("closed", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("merged", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("created", models.DateTimeField(db_index=True)),
                ("modified", models.DateTimeField(db_index=True)),
                ("data", models.JSONField(default=dict)),
                (
                    "library",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="pull_requests",
                        to="libraries.library",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Issue",
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
                ("title", models.CharField(max_length=255)),
                ("number", models.IntegerField()),
                ("github_id", models.CharField(db_index=True, max_length=100)),
                ("is_open", models.BooleanField(db_index=True, default=False)),
                ("closed", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("created", models.DateTimeField(db_index=True)),
                ("modified", models.DateTimeField(db_index=True)),
                ("data", models.JSONField(default=dict)),
                (
                    "library",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="issues",
                        to="libraries.library",
                    ),
                ),
            ],
        ),
    ]
