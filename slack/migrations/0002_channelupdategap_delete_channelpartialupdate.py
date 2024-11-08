# Generated by Django 4.2.16 on 2024-11-08 21:39

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("slack", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ChannelUpdateGap",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("oldest_message_ts", models.CharField(max_length=32, null=True)),
                ("newest_message_ts", models.CharField(max_length=32, null=True)),
                (
                    "channel",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="slack.channel"
                    ),
                ),
            ],
        ),
        migrations.DeleteModel(
            name="ChannelPartialUpdate",
        ),
    ]
