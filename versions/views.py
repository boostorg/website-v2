from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework import permissions
from versions.permissions import SuperUserOrVersionManager

from versions.models import Version, VersionFile
from versions.serializers import VersionSerializer, VersionFileSerializer


class VersionViewSet(viewsets.ModelViewSet):
    model = Version
    queryset = Version.objects.all()
    serializer_class = VersionSerializer
    permission_classes = [permissions.IsAuthenticated, SuperUserOrVersionManager]

class VersionFileViewSet(viewsets.ModelViewSet):
    model = VersionFile
    queryset = VersionFile.objects.all()
    serializer_class = VersionFileSerializer
    permission_classes = [permissions.IsAuthenticated, SuperUserOrVersionManager]
