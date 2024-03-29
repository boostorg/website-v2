# Generated by Django 4.2.2 on 2023-11-03 17:52

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0011_alter_user_image"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="can_update_image",
            field=models.BooleanField(
                default=True,
                help_text="Designates whether the user can update their profile photo. To turn off a user's ability to update their own profile photo, uncheck this box.",
                verbose_name="can_update_image",
            ),
        ),
    ]
