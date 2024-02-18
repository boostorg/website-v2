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

    dependencies = [
        ("versions", "0005_version_active"),
        ("libraries", "0003_library_slug"),
    ]

    operations = [
        migrations.CreateModel(
            name="LibraryVersion",
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
                    "library",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="library_version",
                        to="libraries.library",
                    ),
                ),
                (
                    "version",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="library_version",
                        to="versions.version",
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="library",
            name="versions",
            field=models.ManyToManyField(
                related_name="libraries",
                through="libraries.LibraryVersion",
                to="versions.Version",
            ),
        ),
    ]
