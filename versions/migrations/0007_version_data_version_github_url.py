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
        ("versions", "0006_version_slug"),
    ]

    operations = [
        migrations.AddField(
            model_name="version",
            name="data",
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name="version",
            name="github_url",
            field=models.URLField(
                blank=True,
                help_text="The URL of the Boost version's GitHub repository.",
                max_length=500,
                null=True,
            ),
        ),
    ]
