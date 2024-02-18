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
        ("versions", "0009_alter_version_release_date"),
    ]

    operations = [
        migrations.AddField(
            model_name="version",
            name="beta",
            field=models.BooleanField(
                default=False, help_text="Whether this is a beta release"
            ),
        ),
    ]
