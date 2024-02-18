#
# Copyright (c) 2024 The C++ Alliance, Inc. (https://cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/boostorg/website-v2
#
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
