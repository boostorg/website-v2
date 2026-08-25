from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0028_user_displayed_profile_role_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="GithubActivity",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("data", models.JSONField(blank=True, default=dict)),
                ("last_synced", models.DateTimeField(blank=True, null=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="github_activity",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "GitHub Activity",
                "verbose_name_plural": "GitHub Activities",
            },
        ),
    ]
