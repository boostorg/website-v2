#
# Copyright (c) 2024 The C++ Alliance, Inc. (https://cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/boostorg/website-v2
#

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("libraries", "0004_auto_20230130_1830"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="library",
            name="maintainers",
        ),
        migrations.AddField(
            model_name="libraryversion",
            name="maintainers",
            field=models.ManyToManyField(
                related_name="maintainers", to=settings.AUTH_USER_MODEL
            ),
        ),
    ]
