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
    ]

    operations = [
        migrations.RemoveField(
            model_name="versionfile",
            name="file",
        ),
        migrations.AddField(
            model_name="versionfile",
            name="display_name",
            field=models.CharField(blank=True, max_length=256, null=True),
        ),
        migrations.AddField(
            model_name="versionfile",
            name="url",
            field=models.URLField(default="https://example.com"),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="versionfile",
            name="version",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="downloads",
                to="versions.version",
            ),
        ),
    ]
