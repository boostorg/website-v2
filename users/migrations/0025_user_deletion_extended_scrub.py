from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0024_user_country_user_hide_badges_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="deletion_extended_scrub",
            field=models.BooleanField(default=False, editable=False),
        ),
    ]
