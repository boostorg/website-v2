from django.conf import settings
from django.urls import include, re_path
from django.conf.urls.static import static
from django.contrib import admin
from django.views.generic import TemplateView
from django.urls import path
from rest_framework import routers

from machina import urls as machina_urls

from users.views import (
    UserViewSet,
    CurrentUserView,
    ProfileViewSet,
    ProfilePhotoGitHubUpdateView,
    ProfilePhotoUploadView,
)
from ak.views import (
    HomepageView,
    ForbiddenView,
    InternalServerErrorView,
    NotFoundView,
    OKView,
)
from core.views import MarkdownTemplateView, StaticContentTemplateView
from libraries.views import (
    LibraryList,
    LibraryByCategory,
    LibraryDetail,
    LibraryListByVersion,
    LibraryDetailByVersion,
    LibraryListByVersionByCategory,
)
from libraries.api import LibrarySearchView
from mailing_list.views import MailingListView, MailingListDetailView
from support.views import SupportView, ContactView
from versions.api import VersionViewSet
from versions.views import VersionList, VersionDetail

router = routers.SimpleRouter()

router.register(r"users", UserViewSet, basename="users")
router.register(r"versions", VersionViewSet, basename="versions")
router.register(r"libraries", LibrarySearchView, basename="libraries")


urlpatterns = (
    [
        path("", HomepageView.as_view(), name="home"),
        # scratch template for design scrums
        path(
            "scratch/",
            TemplateView.as_view(template_name="scratch.html"),
            name="scratch",
        ),
        path("admin/", admin.site.urls),
        path("accounts/", include("allauth.urls")),
        path(
            "users/me/update-github-photo/",
            ProfilePhotoGitHubUpdateView.as_view(),
            name="profile-photo-github",
        ),
        path("users/me/photo/", ProfilePhotoUploadView.as_view(), name="profile-photo"),
        path("users/me/", CurrentUserView.as_view(), name="current-user"),
        path("users/<int:pk>/", ProfileViewSet.as_view(), name="profile-user"),
        path("api/v1/", include(router.urls)),
        path("200", OKView.as_view(), name="ok"),
        path("403", ForbiddenView.as_view(), name="forbidden"),
        path("404", NotFoundView.as_view(), name="not_found"),
        path("500", InternalServerErrorView.as_view(), name="internal_server_error"),
        # Temp docs path
        path(
            "docs/",
            TemplateView.as_view(template_name="docs_temp.html"),
            name="docs",
        ),
        path(
            "about/",
            TemplateView.as_view(template_name="boost/about.html"),
            name="boost-about",
        ),
        path("health/", include("health_check.urls")),
        path("forum/", include(machina_urls)),
        path(
            "donate/",
            TemplateView.as_view(template_name="donate/donate.html"),
            name="donate",
        ),
        path(
            "libraries-by-category/<slug:category>/",
            LibraryByCategory.as_view(),
            name="libraries-by-category",
        ),
        path("libraries/", LibraryList.as_view(), name="libraries"),
        path(
            "libraries/<slug:slug>/",
            LibraryDetail.as_view(),
            name="library-detail",
        ),
        path(
            "mailing-list/<int:pk>/",
            MailingListDetailView.as_view(),
            name="mailing-list-detail",
        ),
        path("mailing-list/", MailingListView.as_view(), name="mailing-list"),
        path(
            "people/detail/",
            TemplateView.as_view(template_name="boost/people_detail.html"),
            name="boost-people-detail",
        ),
        path(
            "people/",
            TemplateView.as_view(
                template_name="boost/people.html", extra_context={"range": range(50)}
            ),
            name="boost-people",
        ),
        path(
            "moderators/",
            TemplateView.as_view(
                template_name="boost/moderators.html",
                extra_context={"range": range(50)},
            ),
            name="boost-moderators",
        ),
        path(
            "resources/",
            TemplateView.as_view(template_name="resources/resources.html"),
            name="resources",
        ),
        path(
            "review/past/",
            TemplateView.as_view(template_name="review/past_reviews.html"),
            name="review-past",
        ),
        path(
            "review/request/",
            TemplateView.as_view(template_name="review/review_form.html"),
            name="review-request",
        ),
        path(
            "review/upcoming/",
            TemplateView.as_view(template_name="review/upcoming_reviews.html"),
            name="review-upcoming",
        ),
        path(
            "review/detail/",
            TemplateView.as_view(template_name="review/review_detail.html"),
            name="review-request",
        ),
        path(
            "review/",
            TemplateView.as_view(template_name="review/review_process.html"),
            name="review-process",
        ),
        path(
            "news/detail/",
            TemplateView.as_view(template_name="news/news_detail.html"),
            name="news_detail",
        ),
        path(
            "news/",
            TemplateView.as_view(template_name="news/news_list.html"),
            name="news",
        ),
        # support and contact views
        path("support/", SupportView.as_view(), name="support"),
        path(
            "getting-started/",
            TemplateView.as_view(template_name="support/getting_started.html"),
            name="getting-started",
        ),
        path("contact/", ContactView.as_view(), name="contact"),
        # Boost versions views
        path(
            "versions/<slug:version_slug>/libraries-by-category/<slug:category>/",
            LibraryListByVersionByCategory.as_view(),
            name="libraries-by-version-by-category",
        ),
        path(
            "versions/<slug:slug>/libraries/",
            LibraryListByVersion.as_view(),
            name="libraries-by-version",
        ),
        path(
            "versions/<slug:version_slug>/<slug:slug>/",
            LibraryDetailByVersion.as_view(),
            name="library-detail-by-version",
        ),
        path("versions/<slug:slug>/", VersionDetail.as_view(), name="version-detail"),
        path("versions/", VersionList.as_view(), name="version-list"),
    ]
    + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    + [
        # Markdown content
        re_path(
            r"^markdown/(?P<content_path>.+)/?",
            MarkdownTemplateView.as_view(),
            name="markdown-page",
        ),
        # Static content
        re_path(
            r"^(?P<content_path>.+)/?",
            StaticContentTemplateView.as_view(),
            name="static-content-page",
        ),
    ]
)
