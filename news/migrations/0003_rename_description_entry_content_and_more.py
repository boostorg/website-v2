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
        ("news", "0002_entry_approved_at_entry_moderator_entry_modified_at"),
    ]

    operations = [
        migrations.RenameField(
            model_name="entry",
            old_name="description",
            new_name="content",
        ),
        migrations.RemoveField(
            model_name="blogpost",
            name="body",
        ),
        migrations.AlterField(
            model_name="entry",
            name="external_url",
            field=models.URLField(blank=True, default="", verbose_name="URL"),
        ),
    ]
