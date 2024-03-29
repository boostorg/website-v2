# Generated by Django 3.2.2 on 2022-05-28 19:07

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("versions", "0003_auto_20220528_1905"),
    ]

    operations = [
        migrations.CreateModel(
            name="Version",
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
                ("name", models.CharField(help_text="Version name", max_length=256)),
                ("release_date", models.DateField()),
                ("description", models.TextField(blank=True)),
            ],
        ),
        migrations.CreateModel(
            name="VersionFile",
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
                (
                    "operating_system",
                    models.CharField(
                        choices=[("Unix", "Unix"), ("Windows", "Windows")],
                        default="Unix",
                        max_length=15,
                    ),
                ),
                (
                    "checksum",
                    models.CharField(default=None, max_length=64, unique=True),
                ),
                ("file", models.FileField(upload_to="uploads/")),
                (
                    "version",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="files",
                        to="versions.version",
                    ),
                ),
            ],
        ),
    ]
