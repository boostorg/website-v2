from rest_framework import viewsets
from rest_framework import permissions
from versions.permissions import SuperUserOrVersionManager

from versions.models import Version
from versions.serializers import VersionSerializer

from django.http import JsonResponse
from django.views import View
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from versions.tasks import import_versions


@method_decorator(staff_member_required, name="dispatch")
class ImportVersionsView(View):
    """
    API view to import versions, accessible only to staff and superusers.
    """

    def post(self, request, *args, **kwargs):
        import_versions.delay(new_versions_only=True)
        return JsonResponse({"status": "Importing versions..."}, status=200)


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
