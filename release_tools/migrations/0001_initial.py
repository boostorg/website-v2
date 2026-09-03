from django.db import migrations


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("versions", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReleaseLibraryData",
            fields=[],
            options={
                "verbose_name": "release library data",
                "verbose_name_plural": "Library data",
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=("versions.version",),
        ),
    ]
