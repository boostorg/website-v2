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
        ("libraries", "0017_merge_20230919_2029"),
    ]

    operations = [
        migrations.AddField(
            model_name="libraryversion",
            name="missing_docs",
            field=models.BooleanField(
                default=False,
                help_text="If true, then there are not docs for this version of this library.",
            ),
        ),
    ]
