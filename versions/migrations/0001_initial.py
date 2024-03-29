# Generated by Django 3.2.2 on 2021-11-21 08:28

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

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
                (
                    "checksum",
                    models.CharField(default=None, max_length=64, unique=True),
                ),
                ("file", models.FileField(upload_to="uploads/")),
                ("release_date", models.DateField()),
            ],
        ),
    ]
