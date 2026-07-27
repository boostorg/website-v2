from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0023_user_biography_user_tagline"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="deletion_extended_scrub",
            field=models.BooleanField(default=False, editable=False),
        ),
    ]
