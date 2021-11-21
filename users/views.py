from rest_framework import viewsets
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from .serializers import UserSerializer, FullUserSerializer, CurrentUserSerializer

from .permissions import CustomUserPermissions
from .models import User


class UserViewSet(viewsets.ModelViewSet):
    """
    Main User API ViewSet
    """

    queryset = User.objects.all()
    permission_classes = [CustomUserPermissions]

    def get_serializer_class(self):
        """Pick the right serializer based on the user"""
        if self.request.user.is_staff or self.request.user.is_superuser:
            return FullUserSerializer
        else:
            return UserSerializer


class CurrentUserView(generics.RetrieveUpdateAPIView):
    """
    This gives the current user a convenient way to retrieve or
    update slightly more detailed information about themselves.

    Typically set to a route of `/api/v1/user/me`
    """

    serializer_class = CurrentUserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user
