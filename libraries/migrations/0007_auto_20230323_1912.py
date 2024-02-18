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
        ("libraries", "0006_library_key"),
    ]

    operations = [
        migrations.AlterField(
            model_name="library",
            name="description",
            field=models.TextField(
                blank=True, help_text="The description of the library.", null=True
            ),
        ),
        migrations.AlterField(
            model_name="library",
            name="github_url",
            field=models.URLField(
                blank=True,
                help_text="The URL of the library's GitHub repository.",
                max_length=500,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="library",
            name="key",
            field=models.CharField(
                blank=True,
                help_text="The key of the library as defined in libraries.json.",
                max_length=100,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="library",
            name="name",
            field=models.CharField(
                db_index=True,
                help_text="The name of the library as defined in libraries.json.",
                max_length=100,
            ),
        ),
        migrations.AlterField(
            model_name="library",
            name="slug",
            field=models.SlugField(
                blank=True,
                help_text="The slug of the library, used in the URL.",
                null=True,
            ),
        ),
    ]
