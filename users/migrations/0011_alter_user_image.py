#
# Copyright (c) 2024 The C++ Alliance, Inc. (https://cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/boostorg/website-v2
#

import core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0010_preferences"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="image",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to="profile-images",
                validators=[
                    core.validators.FileTypeValidator(
                        extensions=[".jpg", ".jpeg", ".png"]
                    ),
                    core.validators.MaxFileSizeValidator(max_size=1048576),
                ],
            ),
        ),
    ]
