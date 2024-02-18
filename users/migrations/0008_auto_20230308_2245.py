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
        ("users", "0007_user_image"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="claimed",
            field=models.BooleanField(
                default=True,
                help_text="Designates whether this user has been claimed.",
                verbose_name="claimed",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="valid_email",
            field=models.BooleanField(
                default=True,
                help_text="Designates whether this user's email address is valid, to the best of our knowledge.",
                verbose_name="valid_email",
            ),
        ),
    ]
