from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.generic import TemplateView
from rest_framework import routers

from ak.views import (
    ForbiddenView,
    HomepageBetaView,
    HomepageView,
    InternalServerErrorView,
    NotFoundView,
    OKView,
)
from core.views import (
    CalendarView,
    ClearCacheView,
    DocLibsTemplateView,
    ImageView,
    MarkdownTemplateView,
    StaticContentTemplateView,
    UserGuideTemplateView,
)
from libraries.api import LibrarySearchView
from libraries.views import (
    LibraryDetail,
    LibraryList,
    LibraryListByCategory,
    LibraryListMini,
)
from mailing_list.views import MailingListDetailView, MailingListView
from news.feeds import AtomNewsFeed, RSSNewsFeed
from news.views import (
    AllTypesCreateView,
    BlogPostCreateView,
    BlogPostListView,
    EntryApproveView,
    EntryDeleteView,
    EntryDetailView,
    EntryListView,
    EntryModerationListView,
    EntryUpdateView,
    LinkCreateView,
    LinkListView,
    NewsCreateView,
    NewsListView,
    PollCreateView,
    PollListView,
    VideoCreateView,
    VideoListView,
)
from users.views import (
    CurrentUserAPIView,
    CurrentUserProfileView,
    CustomLoginView,
    CustomSocialSignupViewView,
    CustomSignupView,
    ProfileView,
    UserViewSet,
    UserAvatar,
)
from versions.api import ImportVersionsView, VersionViewSet
from versions.feeds import AtomVersionFeed, RSSVersionFeed
from versions.views import VersionCurrentReleaseDetail, VersionDetail

router = routers.SimpleRouter()

router.register(r"users", UserViewSet, basename="users")
router.register(r"versions", VersionViewSet, basename="versions")
router.register(r"libraries", LibrarySearchView, basename="libraries")


urlpatterns = (
    [
        path("", HomepageView.as_view(), name="home"),
        path("homepage-beta/", HomepageBetaView.as_view(), name="home-beta"),
        path("admin/", admin.site.urls),
        path("oauth2/", include("oauth2_provider.urls", namespace="oauth2_provider")),
        path("feed/downloads.rss", RSSVersionFeed(), name="downloads_feed_rss"),
        path("feed/downloads.atom", AtomVersionFeed(), name="downloads_feed_atom"),
        path("feed/news.rss", RSSNewsFeed(), name="news_feed_rss"),
        path("feed/news.atom", AtomNewsFeed(), name="news_feed_atom"),
        path(
            "accounts/social/signup/",
            CustomSocialSignupViewView.as_view(),
            name="socialaccount_signup",
        ),
        path("accounts/signup/", CustomSignupView.as_view(), name="account_signup"),
        path("accounts/login/", CustomLoginView.as_view(), name="account_login"),
        path("accounts/", include("allauth.urls")),
        path("users/me/", CurrentUserProfileView.as_view(), name="profile-account"),
        path("users/<int:pk>/", ProfileView.as_view(), name="profile-user"),
        path("users/avatar/", UserAvatar.as_view(), name="user-avatar"),
        path("api/v1/users/me/", CurrentUserAPIView.as_view(), name="current-user"),
        path(
            "api/v1/import-versions/",
            ImportVersionsView.as_view(),
            name="import-versions",
        ),
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
        path("health/", include("health_check.urls")),
        # temp page for community until mailman is done.
        path(
            "community/",
            TemplateView.as_view(template_name="community_temp.html"),
            name="community",
        ),
        # Boost community calendar
        path("calendar/", CalendarView.as_view(), name="calendar"),
        # Boost versions views
        path("releases/<slug:slug>/", VersionDetail.as_view(), name="release-detail"),
        path(
            "releases/",
            VersionCurrentReleaseDetail.as_view(),
            name="releases-most-recent",
        ),
        path(
            "donate/",
            TemplateView.as_view(template_name="donate/donate.html"),
            name="donate",
        ),
        path(
            "style-guide/",
            TemplateView.as_view(template_name="style_guide.html"),
            name="donate",
        ),
        path(
            "libraries/by-category/",
            LibraryListByCategory.as_view(),
            name="libraries-by-category",
        ),
        path("libraries/mini/", LibraryListMini.as_view(), name="libraries-mini"),
        path("libraries/", LibraryList.as_view(), name="libraries"),
        path(
            "libraries/<slug:slug>/<slug:version_slug>/",
            LibraryDetail.as_view(),
            name="library-detail-by-version",
        ),
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
        path("news/", EntryListView.as_view(), name="news"),
        path("news/blogpost/", BlogPostListView.as_view(), name="news-blogpost-list"),
        path("news/link/", LinkListView.as_view(), name="news-link-list"),
        path("news/news/", NewsListView.as_view(), name="news-news-list"),
        path("news/poll/", PollListView.as_view(), name="news-poll-list"),
        path("news/video/", VideoListView.as_view(), name="news-video-list"),
        path("news/add/", AllTypesCreateView.as_view(), name="news-create"),
        path("news/add/news/", NewsCreateView.as_view(), name="news-news-create"),
        path(
            "news/add/blogpost/",
            BlogPostCreateView.as_view(),
            name="news-blogpost-create",
        ),
        path("news/add/link/", LinkCreateView.as_view(), name="news-link-create"),
        path("news/add/poll/", PollCreateView.as_view(), name="news-poll-create"),
        path("news/add/video/", VideoCreateView.as_view(), name="news-video-create"),
        path("news/moderate/", EntryModerationListView.as_view(), name="news-moderate"),
        path("news/entry/<slug:slug>/", EntryDetailView.as_view(), name="news-detail"),
        path(
            "news/entry/<slug:slug>/approve/",
            EntryApproveView.as_view(),
            name="news-approve",
        ),
        path(
            "news/entry/<slug:slug>/delete/",
            EntryDeleteView.as_view(),
            name="news-delete",
        ),
        path(
            "news/entry/<slug:slug>/update/",
            EntryUpdateView.as_view(),
            name="news-update",
        ),
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
            "privacy/",
            TemplateView.as_view(template_name="privacy_temp.html"),
            name="privacy",
        ),
        path(
            "terms-of-use/",
            TemplateView.as_view(template_name="terms_of_use.html"),
            name="terms-of-use",
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
            "getting-started/",
            TemplateView.as_view(template_name="support/getting_started.html"),
            name="getting-started",
        ),
        # Internal functions
        path("internal/clear-cache/", ClearCacheView.as_view(), name="clear-cache"),
    ]
    + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    + [
        # Libraries docs, some HTML parts are re-written
        re_path(
            r"^doc/libs/(?P<content_path>.+)/?",
            DocLibsTemplateView.as_view(),
            name="docs-libs-page",
        ),
        # TODO: Greg - determine correct route for user-guide
        re_path(
            r"^doc/(?P<content_path>.+)/?",
            UserGuideTemplateView.as_view(),
            name="docs-user-guide",
        ),
        # Markdown content
        re_path(
            r"^markdown/(?P<content_path>.+)/?",
            MarkdownTemplateView.as_view(),
            name="markdown-page",
        ),
        # Images from static content
        re_path(
            r"^images/(?P<content_path>.+)/?",
            ImageView.as_view(),
            name="images-page",
        ),
        # Static content
        re_path(
            r"^(?P<content_path>.+)/?",
            StaticContentTemplateView.as_view(),
            name="static-content-page",
        ),
    ]
)

handler404 = "ak.views.custom_404_view"
