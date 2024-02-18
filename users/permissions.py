#
# Copyright (c) 2024 The C++ Alliance, Inc. (https://cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/boostorg/website-v2
#
from rest_framework import permissions


class CustomUserPermissions(permissions.BasePermission):
    """
    Custom user API permissions.

    - Normal users can only list and retrieve users
    - Admins and Superusers can do everything

    We rely on the API view itself to give the right type of
    user the right serializer to avoid disclosing sensitive information.
    """

    def has_permission(self, request, view):
        # allow all POST/DELETE/PUT requests
        if (
            request.method == "POST"
            or request.method == "DELETE"
            or request.method == "PUT"
        ):
            if request.user.is_staff or request.user.is_superuser:
                return True
            else:
                return False

        return request.user.is_authenticated
