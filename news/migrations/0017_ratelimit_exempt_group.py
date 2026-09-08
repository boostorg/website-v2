from django.db import migrations

# Spelled out rather than imported from `news.constants`: a historical migration
# has to keep seeding the names it shipped with, whatever the constants say
# later.
GROUP_NAME = "ratelimit_exempt"
PERMISSION_CODENAME = "bypass_description_generation_limit"


def create_ratelimit_exempt_group(apps, schema_editor):
    """Seed the exemption group and grant it the bypass permission.

    The permission is created explicitly rather than looked up: Django creates
    model permissions in a `post_migrate` signal, which fires after the whole
    migrate run, so on a fresh database the auto-created row does not exist yet
    and the group would end up with no permission at all.
    """
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")
    Group = apps.get_model("auth", "Group")

    content_type, _ = ContentType.objects.get_or_create(
        app_label="news", model="descriptiongenerationattempt"
    )
    permission, _ = Permission.objects.get_or_create(
        codename=PERMISSION_CODENAME,
        content_type=content_type,
        defaults={"name": "Can bypass the AI description daily limit"},
    )
    group, _ = Group.objects.get_or_create(name=GROUP_NAME)
    group.permissions.add(permission)


class Migration(migrations.Migration):
    dependencies = [
        ("news", "0016_aidescriptionsettings_descriptiongenerationattempt"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        # Reversible, but deliberately not by deleting: the group may predate
        # this migration or have been given memberships and unrelated
        # permissions since, and a rollback must not take those with it. The
        # permission itself goes when the model does.
        migrations.RunPython(create_ratelimit_exempt_group, migrations.RunPython.noop),
    ]
