# Generated by Django 3.2.2 on 2022-05-28 20:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("versions", "0004_version_versionfile"),
    ]

    operations = [
        migrations.AddField(
            model_name="version",
            name="active",
            field=models.BooleanField(
                default=True,
                help_text="Control whether or not this version is available on the website",
            ),
        ),
    ]
