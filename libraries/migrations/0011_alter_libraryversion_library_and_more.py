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
        ("versions", "0007_version_data_version_github_url"),
        ("libraries", "0010_commitdata"),
    ]

    operations = [
        migrations.AlterField(
            model_name="libraryversion",
            name="library",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="library_version",
                to="libraries.library",
            ),
        ),
        migrations.AlterField(
            model_name="libraryversion",
            name="version",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="library_version",
                to="versions.version",
            ),
        ),
    ]
