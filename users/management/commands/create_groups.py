from django.contrib.auth.models import Group, Permission
from django.core.management import BaseCommand


class Command(BaseCommand):
    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)

    help = "Create default groups"

    def handle(self, *args, **options):
        Group.objects.get(name="version_manager").delete()
        # Code to add permission to group ???
        # ct = ContentType.objects.get_for_model(Version)

        # Now what - Say I want to add 'Can add version' permission to new_group?
        Permission.objects.get(codename="can_add_version").delete()
        # new_group.permissions.add(permission)
