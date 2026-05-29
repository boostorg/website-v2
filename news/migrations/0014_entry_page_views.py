from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("news", "0013_video_thumbnail"),
    ]

    operations = [
        migrations.AddField(
            model_name="entry",
            name="page_views",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
