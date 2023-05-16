# Generated by Django 4.2 on 2023-05-10 21:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("versions", "0006_version_slug"),
    ]

    operations = [
        migrations.AddField(
            model_name="version",
            name="data",
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name="version",
            name="github_url",
            field=models.URLField(
                blank=True,
                help_text="The URL of the Boost version's GitHub repository.",
                max_length=500,
                null=True,
            ),
        ),
    ]