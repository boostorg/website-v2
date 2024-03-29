# Generated by Django 4.2.2 on 2023-11-02 19:32

import core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("news", "0007_alter_entry_external_url_alter_entry_slug"),
    ]

    operations = [
        migrations.AlterField(
            model_name="entry",
            name="image",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to="news/%Y/%m/",
                validators=[
                    core.validators.FileTypeValidator(
                        extensions=[".jpg", ".jpeg", ".png"]
                    ),
                    core.validators.MaxFileSizeValidator(max_size=1048576),
                ],
            ),
        ),
    ]
