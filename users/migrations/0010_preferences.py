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
import django.db.models.deletion
import users.models


def backfill_preferences(apps, schema_editor):
    User = apps.get_model('users', 'User')
    Preferences = apps.get_model('users', 'Preferences')
    instances = [Preferences(user=u) for u in User.objects.all()]
    Preferences.objects.bulk_create(instances)


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0009_user_display_name"),
    ]

    operations = [
        migrations.CreateModel(
            name="Preferences",
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
                    "notifications",
                    models.JSONField(default=users.models.get_empty_notifications),
                ),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="preferences",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.RunPython(backfill_preferences, lambda *args, **kwargs: None),
    ]
