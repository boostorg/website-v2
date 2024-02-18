#
# Copyright (c) 2024 The C++ Alliance, Inc. (https://cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/boostorg/website-v2
#

from django.db import migrations

# 2023 removing forums
# def gen_default_forum(apps, schema_editor):
#     forum = apps.get_model("forum", "Forum")
#     forum.objects.create(
#         name="Intial Forum",
#         type=0,
#         slug="initial-forum",
#         lft=1,
#         rght=2,
#         tree_id=1,
#         level=0,
#     )


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0003_alter_user_data"),
    ]

    operations = [
        # # omit reverse_code=... if you don't want the migration to be reversible.
        # migrations.RunPython(gen_default_forum, reverse_code=migrations.RunPython.noop),
    ]
