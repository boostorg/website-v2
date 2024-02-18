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
        ("users", "0011_alter_user_image"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="can_update_image",
            field=models.BooleanField(
                default=True,
                help_text="Designates whether the user can update their profile photo. To turn off a user's ability to update their own profile photo, uncheck this box.",
                verbose_name="can_update_image",
            ),
        ),
    ]
