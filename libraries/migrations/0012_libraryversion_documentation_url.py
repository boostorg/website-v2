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
        ("libraries", "0011_alter_libraryversion_library_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="libraryversion",
            name="documentation_url",
            field=models.CharField(
                blank=True,
                help_text="The path to the docs for this library version.",
                max_length=255,
                null=True,
            ),
        ),
    ]
