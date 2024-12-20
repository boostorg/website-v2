# Generated by Django 4.2.16 on 2024-11-13 19:05

from django.db import migrations, models
import django.db.models.functions.comparison
import slack.models


class Migration(migrations.Migration):

    dependencies = [
        ("slack", "0001_initial"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="thread",
            index=models.Index(
                slack.models.ToTimestamp(
                    django.db.models.functions.comparison.Cast(
                        "last_update_ts", output_field=models.FloatField()
                    )
                ),
                name="last_update_as_datetime",
            ),
        ),
    ]
