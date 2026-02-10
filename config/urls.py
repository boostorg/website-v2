import logging

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path, register_converter, reverse_lazy
from django.views.generic import TemplateView
from django.views.generic.base import RedirectView
from rest_framework import routers
from wagtail import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls

from ak.views import (
    ForbiddenView,
    HomepageView,
    InternalServerErrorView,
    NotFoundView,
    OKView,
)
from config.settings import DEBUG_TOOLBAR
from core.views import (
    BSLView,
    CalendarView,
    ClearCacheView,
    DocLibsTemplateView,
    ImageView,
    MarkdownTemplateView,
    RedirectToDocsView,
    RedirectToHTMLDocsView,
    RedirectToHTMLToolsView,
    RedirectToLibrariesView,
    RedirectToReleaseView,
    RedirectToToolsView,
    StaticContentTemplateView,
    UserGuideTemplateView,
    BoostDevelopmentView,
    ModernizedDocsView,
    RedirectToLibraryDetailView,
)
from marketing.views import PlausibleRedirectView, WhitePaperView
from libraries.api import LibrarySearchView
from libraries.views import (
    LibraryDetail,
    LibraryListDispatcher,
    LibraryMissingVersionView,
    CommitAuthorEmailCreateView,
    VerifyCommitEmailView,
    CommitEmailResendView,
)
from news.feeds import AtomNewsFeed, RSSNewsFeed
from news.views import (
    AllTypesCreateView,
    BlogPostCreateView,
    BlogPostListView,
    EntryApproveView,
    EntryDeleteView,
    EntryDetailView,
    EntryListView,
    EntryModerationDetailView,
    EntryModerationListView,
    EntryModerationMagicApproveView,
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
    CustomEmailVerificationSentView,
    CustomLoginView,
    CustomSignupView,
    CustomSocialSignupViewView,
    UserViewSet,
    UserAvatar,
    DeleteUserView,
    CancelDeletionView,
    DeleteImmediatelyView,
)
from versions.api import ImportVersionsView, VersionViewSet
from versions.converters import BoostVersionSlugConverter
from versions.feeds import AtomVersionFeed, RSSVersionFeed
from versions.views import (
    InProgressReleaseNotesView,
    PastReviewListView,
    ScheduledReviewListView,
    VersionDetail,
    ReportPreviewView,
    ReportPreviewGenerateView,
)

djdt_urls = []
try:
    if DEBUG_TOOLBAR:
        from debug_toolbar.toolbar import debug_toolbar_urls

        djdt_urls = debug_toolbar_urls()
except ModuleNotFoundError:
    logging.error(
        "DEBUG_TOOLBAR enabled but Django Debug Toolbar not installed. Run `just build`"
    )

register_converter(BoostVersionSlugConverter, "boostversionslug")

router = routers.SimpleRouter()

router.register(r"users", UserViewSet, basename="users")
router.register(r"versions", VersionViewSet, basename="versions")
router.register(r"libraries", LibrarySearchView, basename="libraries")

urlpatterns = (
    [
        path("", HomepageView.as_view(), name="home"),
        path("admin/", admin.site.urls),
        path("oauth2/", include("oauth2_provider.urls", namespace="oauth2_provider")),
        path("feed/downloads.rss", RSSVersionFeed(), name="downloads_feed_rss"),
        path("feed/downloads.atom", AtomVersionFeed(), name="downloads_feed_atom"),
        path("feed/news.rss", RSSNewsFeed(), name="news_feed_rss"),
        path("feed/news.atom", AtomNewsFeed(), name="news_feed_atom"),
        path("LICENSE_1_0.txt", BSLView, name="license"),
        path(
            "qrc/<str:campaign_identifier>/",
            PlausibleRedirectView.as_view(),
            name="qr_code_root",
        ),  # just in case
        path(
            "qrc/<str:campaign_identifier>/<path:main_path>",
            PlausibleRedirectView.as_view(),
            name="qr_code",
        ),
        path(
            "bsm/<str:campaign_identifier>/",
            PlausibleRedirectView.as_view(),
            name="bsm_root",
        ),
        path(
            "bsm/<str:campaign_identifier>/<path:main_path>",
            PlausibleRedirectView.as_view(),
            name="bsm",
        ),
        path(
            "outreach/<slug:category>/<slug:slug>",
            WhitePaperView.as_view(),
            name="whitepaper",
        ),
        path(
            "accounts/social/signup/",
            CustomSocialSignupViewView.as_view(),
            name="socialaccount_signup",
        ),
        path("accounts/signup/", CustomSignupView.as_view(), name="account_signup"),
        path("accounts/login/", CustomLoginView.as_view(), name="account_login"),
        path(
            "accounts/confirm-email/",
            CustomEmailVerificationSentView.as_view(),
            name="account_confirm_email",
        ),
        path("accounts/", include("allauth.urls")),
        path("users/me/", CurrentUserProfileView.as_view(), name="profile-account"),
        path("users/me/delete/", DeleteUserView.as_view(), name="profile-delete"),
        path(
            "users/me/cancel-delete/",
            CancelDeletionView.as_view(),
            name="profile-cancel-delete",
        ),
        path(
            "users/me/delete-immediately/",
            DeleteImmediatelyView.as_view(),
            name="profile-delete-immediately",
        ),
        # Return a 404 for now. Profile view is not ready.
        # path("users/<int:pk>/", ProfileView.as_view(), name="profile-user"),
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
        path("asciidoctor_sandbox/", include("asciidoctor_sandbox.urls")),
        # temp page for community until mailman is done.
        path(
            "community/",
            TemplateView.as_view(template_name="community.html"),
            name="community",
        ),
        # Boost community calendar
        path("calendar/", CalendarView.as_view(), name="calendar"),
        path(
            "boost-development/",
            BoostDevelopmentView.as_view(),
            name="boost-development",
        ),
        # Boost versions views
        path("releases/", VersionDetail.as_view(), name="releases-most-recent"),
        path(
            "releases/boost-in-progress/",
            InProgressReleaseNotesView.as_view(),
            name="release-in-progress",
        ),
        path(
            "releases/<boostversionslug:version_slug>/",
            VersionDetail.as_view(),
            name="release-detail",
        ),
        path(
            "releases/<boostversionslug:version_slug>/report",
            ReportPreviewView.as_view(),
            name="release-report-preview",
        ),
        path(
            "releases/<boostversionslug:version_slug>/report/generate",
            ReportPreviewGenerateView.as_view(),
            name="release-report-generate",
        ),
        path(
            "donate/",
            TemplateView.as_view(template_name="donate/donate.html"),
            name="donate",
        ),
        path(
            "style-guide/",
            TemplateView.as_view(template_name="style_guide.html"),
            name="style-guide",
        ),
        path("libraries/", LibraryListDispatcher.as_view(), name="libraries"),
        path(
            "libraries/<boostversionslug:version_slug>/<str:library_view_str>/",
            LibraryListDispatcher.as_view(),
            name="libraries-list",
        ),
        path(
            "libraries/<boostversionslug:version_slug>/<str:library_view_str>/<slug:category_slug>/",
            LibraryListDispatcher.as_view(),
            name="libraries-list",
        ),
        path(
            "library/<boostversionslug:version_slug>/<slug:library_slug>/",
            LibraryDetail.as_view(),
            name="library-detail",
        ),
        path(
            "library/<boostversionslug:version_slug>/<slug:library_slug>/missing/",
            LibraryMissingVersionView.as_view(),
            name="library-detail-version-missing",
        ),
        path(
            "libraries/commit_author_email_create/",
            CommitAuthorEmailCreateView.as_view(),
            name="commit-author-email-create",
        ),
        path(
            "libraries/commit_author_email_verify/<str:token>/",
            VerifyCommitEmailView.as_view(),
            name="commit-author-email-verify",
        ),
        path(
            "libraries/resend_author_email_verify/<uuid:claim_hash>/",
            CommitEmailResendView.as_view(),
            name="commit-author-email-verify-resend",
        ),
        # Redirect for '/libs/' legacy boost.org urls.
        re_path(
            r"^libs/(?P<library_slug>[-\w]+)/?$",
            LibraryDetail.as_view(redirect_to_docs=True),
            name="library-docs-redirect",
        ),
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
        path(
            "news/moderate/<slug:slug>/",
            EntryModerationDetailView.as_view(),
            name="news-moderate-detail",
        ),
        path(
            "news/moderate/magic/<str:token>/",
            EntryModerationMagicApproveView.as_view(),
            name="news-magic-approve",
        ),
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
            MarkdownTemplateView.as_view(),
            name="privacy",
            kwargs={"markdown_local": "privacy-policy"},
        ),
        path(
            "terms-of-use/",
            MarkdownTemplateView.as_view(),
            name="terms-of-use",
            kwargs={"markdown_local": "terms-of-use"},
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
            PastReviewListView.as_view(),
            name="review-past",
        ),
        path(
            "review/request/",
            TemplateView.as_view(template_name="review/review_form.html"),
            name="review-request",
        ),
        path(
            "review/upcoming/",
            ScheduledReviewListView.as_view(),
            name="review-upcoming",
        ),
        path(
            "review/detail/",
            TemplateView.as_view(template_name="review/review_detail.html"),
            name="review-request",
        ),
        path(
            "review/",
            RedirectView.as_view(
                url=reverse_lazy(
                    "docs-user-guide",
                    kwargs={"content_path": "formal-reviews/submissions.html"},
                ),
                permanent=True,
            ),
            name="review-process",
        ),
        path(
            "getting-started/",
            TemplateView.as_view(template_name="support/getting_started.html"),
            name="getting-started",
        ),
        # Internal functions
        path("internal/clear-cache/", ClearCacheView.as_view(), name="clear-cache"),
        path(
            "internal/modernized-docs/<path:content_path>",
            ModernizedDocsView.as_view(),
            name="modernized_docs",
        ),
        # Wagtail stuff
        path("cms/", include(wagtailadmin_urls)),
        path("documents/", include(wagtaildocs_urls)),
        # Custom Django views (must come before Wagtail catch-all)
        path("testimonials/", include("testimonials.urls")),
    ]
    + [
        re_path(
            r"^lib/(?P<library_slug>[^/]+)/?$",
            RedirectToLibraryDetailView.as_view(),
            name="redirect-to-library-view",
        ),
        path(
            "libraries/<str:requested_version>/",
            RedirectToLibrariesView.as_view(),
            name="redirect-to-library-list-view",
        ),
        # Redirects for old boost.org urls.
        re_path(
            r"^libs/(?P<libname>[^/]+)/(?P<path>.*)/?$",
            RedirectToDocsView.as_view(),
            name="redirect-to-latest-lib",
        ),
        re_path(
            r"^doc/html/(?P<libname>[^/]+)/(?P<path>.*)/?$",
            RedirectToHTMLDocsView.as_view(),
            name="redirect-to-latest-html",
        ),
        re_path(
            r"^tools/(?P<libname>[^/]+)/?$",
            RedirectToToolsView.as_view(),
            name="redirect-to-latest-tools",
        ),
        re_path(
            r"^users/history/(?P<requested_version>[^/]+).html/?$",
            RedirectToReleaseView.as_view(),
            name="redirect-to-release",
        ),
        re_path(
            r"^doc/libs/(?P<requested_version>[^/]+)/?$",
            RedirectToLibrariesView.as_view(),
            name="redirect-to-library-page",
        ),
        re_path(
            r"^tools/(?P<libname>[^/]+)/(?P<path>.*)$",
            RedirectToHTMLToolsView.as_view(),
            name="redirect-to-latest-tools-html",
        ),
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
        # Static content (exclude Wagtail paths)
        re_path(
            r"^(?!__debug__|outreach/|testimonials/)(?P<content_path>.+)/?",
            StaticContentTemplateView.as_view(),
            name="static-content-page",
        ),
    ]
    + djdt_urls
    + [
        # Wagtail catch-all (must be last!)
        path("", include(wagtail_urls)),
    ]
)

handler404 = "ak.views.custom_404_view"
