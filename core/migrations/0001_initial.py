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

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="RenderedContent",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "cache_key",
                    models.CharField(
                        db_index=True,
                        help_text="The cache key for the content.",
                        max_length=255,
                        unique=True,
                    ),
                ),
                (
                    "content_type",
                    models.CharField(
                        blank=True,
                        help_text="The content type/MIME type.",
                        max_length=255,
                        null=True,
                    ),
                ),
                (
                    "content_original",
                    models.TextField(
                        blank=True, help_text="The original content.", null=True
                    ),
                ),
                (
                    "content_html",
                    models.TextField(
                        blank=True, help_text="The rendered HTML content.", null=True
                    ),
                ),
                (
                    "last_updated_at",
                    models.DateTimeField(
                        blank=True,
                        help_text="The last time the content was updated in S3.",
                        null=True,
                    ),
                ),
            ],
            options={
                "verbose_name": "rendered content",
                "verbose_name_plural": "rendered contents",
            },
        ),
    ]
