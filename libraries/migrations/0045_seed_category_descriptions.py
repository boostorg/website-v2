from django.db import migrations

from libraries.constants import CATEGORY_DESCRIPTIONS


def seed_descriptions(apps, schema_editor):
    Category = apps.get_model("libraries", "Category")
    for name, description in CATEGORY_DESCRIPTIONS.items():
        Category.objects.filter(name=name, short_description="").update(
            short_description=description
        )


def clear_descriptions(apps, schema_editor):
    Category = apps.get_model("libraries", "Category")
    for name, description in CATEGORY_DESCRIPTIONS.items():
        Category.objects.filter(name=name, short_description=description).update(
            short_description=""
        )


class Migration(migrations.Migration):

    dependencies = [
        ("libraries", "0044_merge_20260814_1905"),
    ]

    operations = [
        migrations.RunPython(seed_descriptions, clear_descriptions),
    ]
