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
        ("versions", "0005_version_active"),
    ]

    operations = [
        migrations.AddField(
            model_name="version",
            name="slug",
            field=models.SlugField(blank=True, null=True),
        ),
    ]
