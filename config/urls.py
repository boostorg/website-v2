from django.conf.urls import include, url
from django.contrib import admin
from django.urls import path
from rest_framework import routers

from machina import urls as machina_urls

from users.views import UserViewSet, CurrentUserView
from ak.views import (
    HomepageView,
    ForbiddenView,
    InternalServerErrorView,
    NotFoundView,
    OKView,
)
from versions.api import VersionViewSet
from versions.views import VersionList, VersionDetail

router = routers.SimpleRouter()

router.register(r"users", UserViewSet, basename="users")
router.register(r"versions", VersionViewSet, basename="versions")


urlpatterns = [
    path("", HomepageView.as_view(), name="home"),
    path("admin/", admin.site.urls),
    path("users/me/", CurrentUserView.as_view(), name="current-user"),
    path("api/v1/", include(router.urls)),
    path("200", OKView.as_view(), name="ok"),
    path("403", ForbiddenView.as_view(), name="forbidden"),
    path("404", NotFoundView.as_view(), name="not_found"),
    path("500", InternalServerErrorView.as_view(), name="internal_server_error"),
    path("health/", include("health_check.urls")),
    path("forum/", include(machina_urls)),
    path("versions/", VersionList.as_view(), name="version-list"),
    path("version/<int:pk>/", VersionDetail.as_view(), name="version-detail"),
]
