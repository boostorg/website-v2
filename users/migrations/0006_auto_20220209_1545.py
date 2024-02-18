#
# Copyright (c) 2024 The C++ Alliance, Inc. (https://cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/boostorg/website-v2
#

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0005_auto_20211121_0908"),
    ]

    operations = [
        migrations.CreateModel(
            name="Badge",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "name",
                    models.CharField(blank=True, max_length=100, verbose_name="name"),
                ),
                (
                    "display_name",
                    models.CharField(
                        blank=True, max_length=100, verbose_name="display name"
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="user",
            name="github_username",
            field=models.CharField(
                blank=True, max_length=100, verbose_name="github username"
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="badges",
            field=models.ManyToManyField(to="users.Badge"),
        ),
    ]
