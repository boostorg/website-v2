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
        ("users", "0002_auto_20171007_1545"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="data",
            field=models.JSONField(
                blank=True, default=dict, help_text="Arbitrary user data"
            ),
        ),
    ]
