from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework import permissions
from versions.permissions import SuperUserOrVersionManager

from versions.models import Version, VersionFile
from versions.serializers import VersionSerializer, VersionFileSerializer


class VersionViewSet(viewsets.ModelViewSet):
    model = Version
    serializer_class = VersionSerializer

    def get_queryset(self):
        if self.request.user.is_authenticated:
            return Version.objects.all()
        else:
            return Version.objects.active()

    def get_permissions(self):
        """
        Allow anyone in the public to view the list of active Versions, but
        only allow SueprUsers or VersionManagers to create or update data
        """
        if self.action == "list":
            return [permissions.AllowAny()]
        else:
            return [permissions.IsAuthenticated(), SuperUserOrVersionManager()]
