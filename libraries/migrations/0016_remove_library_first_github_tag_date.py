# Generated by Django 4.2.2 on 2023-09-08 20:48

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("libraries", "0015_library_data"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="library",
            name="first_github_tag_date",
        ),
    ]
