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
        ("libraries", "0008_alter_libraryversion_library_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="library",
            name="first_github_tag_date",
            field=models.DateField(
                blank=True,
                help_text="The date of the first release, based on the date of the commit of the first GitHub tag.",
                null=True,
            ),
        ),
    ]
