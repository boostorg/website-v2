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
        ("versions", "0008_remove_versionfile_file_versionfile_display_name_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="version",
            name="release_date",
            field=models.DateField(null=True),
        ),
    ]
