from django.conf.urls import include, url
from django.contrib import admin
from django.views.generic import TemplateView
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
from libraries.views import (
    LibraryList,
    LibraryByLetter,
    LibraryByCategory,
    LibraryDetail,
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
    path(
        "libraries-by-letter/<str:letter>/",
        LibraryByLetter.as_view(),
        name="libraries-by-letter",
    ),
    path(
        "libraries-by-category/<slug:category>/",
        LibraryByCategory.as_view(),
        name="libraries-by-category",
    ),
    path("libraries/", LibraryList.as_view(), name="libraries"),
    path(
        "library/<slug:slug>/",
        LibraryDetail.as_view(),
        name="library-detail",
    ),
    path("versions/", VersionList.as_view(), name="version-list"),
    path("version/<int:pk>/", VersionDetail.as_view(), name="version-detail"),
]
