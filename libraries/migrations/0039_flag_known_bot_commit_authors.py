from django.db import migrations
from django.db.models import Q

from libraries.bots import KNOWN_BOT_NAMES


def flag_known_bots(apps, schema_editor):
    CommitAuthor = apps.get_model("libraries", "CommitAuthor")
    name_filter = Q(name__iendswith="[bot]")
    for name in KNOWN_BOT_NAMES:
        name_filter |= Q(name__iexact=name)
    CommitAuthor.objects.filter(name_filter).update(is_bot=True)


def unflag_bots(apps, schema_editor):
    CommitAuthor = apps.get_model("libraries", "CommitAuthor")
    CommitAuthor.objects.filter(is_bot=True).update(is_bot=False)


class Migration(migrations.Migration):

    dependencies = [
        ("libraries", "0038_commitauthor_is_bot"),
    ]

    operations = [
        migrations.RunPython(flag_known_bots, unflag_bots),
    ]
