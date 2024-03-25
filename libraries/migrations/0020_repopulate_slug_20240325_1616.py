from django.db import migrations
from django.utils.text import slugify

from libraries.models import Library


def migrate_to_key_slug(apps, schema_editor):
    """Migrate the key to the slug field."""

    for library in Library.objects.all():
        library.slug = slugify(library.key)
        library.save()


class Migration(migrations.Migration):

    dependencies = [
        ("libraries", "0019_merge_20240218_0058"),
    ]

    operations = [migrations.RunPython(migrate_to_key_slug)]
