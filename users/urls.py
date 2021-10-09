from rest_framework.routers import DefaultRouter

from django.urls import path

from . import api


router = DefaultRouter()
router.register(r"users", api.UserViewSet, basename="user")

urlpatterns = [
    path("users/me/", api.CurrentUserView.as_view(), name="current-user"),
]

urlpatterns += router.urls
