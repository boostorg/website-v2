from django.db import migrations


def populate_tou_preference(apps, schema_editor):
    from users.models import Preferences

    prefs_to_save = []
    for preference in Preferences.objects.all():
        preference.notifications[Preferences.TERMS_CHANGED] = [False]
        prefs_to_save.append(preference)
    Preferences.objects.bulk_update(prefs_to_save, ["notifications"])


def drop_tou_preference(apps, schema_editor):
    from users.models import Preferences

    prefs_to_save = []
    for preference in Preferences.objects.all():
        del preference.notifications[Preferences.TERMS_CHANGED]
        prefs_to_save.append(preference)
    Preferences.objects.bulk_update(prefs_to_save, ["notifications"])


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0013_user_indicate_last_login_method"),
    ]

    operations = [migrations.RunPython(populate_tou_preference, drop_tou_preference)]
