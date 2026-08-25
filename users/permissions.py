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
        # Gate every write method, not an enumerated list, so PATCH can't be
        # left out and a future method can't be added unguarded.
        if request.method not in permissions.SAFE_METHODS:
            return bool(request.user.is_staff or request.user.is_superuser)

        return request.user.is_authenticated
