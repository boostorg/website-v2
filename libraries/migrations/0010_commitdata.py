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
        ("libraries", "0009_library_first_github_tag_date"),
    ]

    operations = [
        migrations.CreateModel(
            name="CommitData",
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
                    "commit_count",
                    models.PositiveIntegerField(
                        default=0,
                        help_text="The number of commits made during the month.",
                    ),
                ),
                (
                    "month_year",
                    models.DateField(
                        help_text="The month and year when the commits were made. "
                        "Day is always set to the first of the month."
                    ),
                ),
                (
                    "branch",
                    models.CharField(
                        default="master",
                        help_text="The GitHub branch to which these commits were made.",
                        max_length=256,
                    ),
                ),
                (
                    "library",
                    models.ForeignKey(
                        help_text="The Library to which these commits belong.",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="commit_data",
                        to="libraries.library",
                    ),
                ),
            ],
            options={
                "unique_together": {("library", "month_year", "branch")},
            },
        ),
    ]
