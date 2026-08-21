from django.db import migrations

from users.utils import generate_routing_key

# UserProfileRoutingKey.KEY_MAX_LENGTH at the time of this migration: class
# attributes are not carried by historical models.
KEY_MAX_LENGTH = 64
BATCH_SIZE = 1000


def backfill_routing_keys(apps, schema_editor):
    """Give every existing user a public profile URL.

    Inactive accounts are included, matching the creation hook, which mints for
    every user regardless of state. Their profiles 404 either way, but a key
    they already have is one less way to break get_absolute_url() if the
    account is ever reactivated.
    """
    User = apps.get_model("users", "User")
    RoutingKey = apps.get_model("users", "UserProfileRoutingKey")

    taken = set(RoutingKey.objects.values_list("routing_key", flat=True))
    already_keyed = set(RoutingKey.objects.values_list("user_id", flat=True))

    batch = []
    users = (
        User.objects.exclude(pk__in=already_keyed)
        .values_list("pk", "display_name")
        .iterator()
    )
    for user_pk, display_name in users:
        # Every user with no usable name shares the "user" base, so collisions
        # within this batch are likely enough to check for rather than assume.
        key = generate_routing_key(display_name, KEY_MAX_LENGTH)
        while key in taken:
            key = generate_routing_key(display_name, KEY_MAX_LENGTH)
        taken.add(key)

        batch.append(RoutingKey(routing_key=key, user_id=user_pk))
        if len(batch) >= BATCH_SIZE:
            RoutingKey.objects.bulk_create(batch)
            batch = []

    if batch:
        RoutingKey.objects.bulk_create(batch)


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0029_userprofileroutingkey"),
    ]

    operations = [
        # Irreversible by design: keys are never reused, so deleting them on
        # reverse would let a re-run hand a URL someone already shared to a
        # different user.
        migrations.RunPython(backfill_routing_keys, migrations.RunPython.noop),
    ]
