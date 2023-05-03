# Generated by Django 4.2.1 on 2023-05-25 18:54

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("news", "0002_entry_approved_at_entry_moderator_entry_modified_at"),
    ]

    operations = [
        migrations.RenameField(
            model_name="entry",
            old_name="description",
            new_name="content",
        ),
        migrations.RemoveField(
            model_name="blogpost",
            name="body",
        ),
        migrations.AlterField(
            model_name="entry",
            name="external_url",
            field=models.URLField(blank=True, default="", verbose_name="URL"),
        ),
    ]