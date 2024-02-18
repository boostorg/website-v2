#
# Copyright (c) 2024 The C++ Alliance, Inc. (https://cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/boostorg/website-v2
#

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
