from django.conf.urls import include, url
from django.contrib import admin
from django.urls import path
from rest_framework import routers
from users.views import UserViewSet, CurrentUserView
from ak.views import (
    HomepageView,
    ForbiddenView,
    InternalServerErrorView,
    NotFoundView,
    OKView,
)
from versions.views import *

router = routers.SimpleRouter()

router.register(r"users", UserViewSet, basename="users")
router.register(r"versions", VersionViewSet, basename="versions")
router.register(r"version-files", VersionFileViewSet, basename="version-files")


urlpatterns = [
    path("", HomepageView.as_view(), name="home"),
    path("admin/", admin.site.urls),
    path("users/me/", CurrentUserView.as_view(), name="current-user"),
    url(r"^api/v1/", include(router.urls)),
    path("200", OKView.as_view(), name="ok"),
    path("403", ForbiddenView.as_view(), name="forbidden"),
    path("404", NotFoundView.as_view(), name="not_found"),
    path("500", InternalServerErrorView.as_view(), name="internal_server_error"),
    path("health/", include("health_check.urls")),
]
