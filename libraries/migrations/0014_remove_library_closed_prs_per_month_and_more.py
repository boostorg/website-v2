#
# Copyright (c) 2024 The C++ Alliance, Inc. (https://cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/boostorg/website-v2
#

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("libraries", "0013_library_featured"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="library",
            name="closed_prs_per_month",
        ),
        migrations.RemoveField(
            model_name="library",
            name="commits_per_release",
        ),
        migrations.RemoveField(
            model_name="library",
            name="first_release",
        ),
        migrations.RemoveField(
            model_name="library",
            name="last_github_update",
        ),
        migrations.RemoveField(
            model_name="library",
            name="open_issues",
        ),
    ]
