from rest_framework.routers import DefaultRouter

from django.urls import path

from . import api
from .views import deactivate_account


router = DefaultRouter()
router.register(r"users", api.UserViewSet, basename="user")

urlpatterns = [
    path("users/me/", api.CurrentUserView.as_view(), name="current-user"),
    path("users/me/delete/", deactivate_account, name="current-user-delete"),
]

urlpatterns += router.urls
