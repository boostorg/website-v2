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
