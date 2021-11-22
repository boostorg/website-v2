from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework import permissions
from versions.permissions import SuperUserOrVersionManager

from versions.models import Version
from versions.serializers import VersionSerializer


class VersionViewSet(viewsets.ModelViewSet):
    model = Version
    queryset = Version.objects.all()
    serializer_class = VersionSerializer
    permission_classes = [permissions.IsAuthenticated, SuperUserOrVersionManager]
