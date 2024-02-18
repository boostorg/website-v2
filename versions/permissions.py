#
# Copyright (c) 2024 The C++ Alliance, Inc. (https://cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/boostorg/website-v2
#
from rest_framework import permissions


def is_version_manager(user):
    return user.groups.filter(name="version_manager").exists()


class SuperUserOrVersionManager(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.user.is_superuser:
            return True

        if is_version_manager(request.user):
            return True

        if request.method in permissions.SAFE_METHODS:
            return True
