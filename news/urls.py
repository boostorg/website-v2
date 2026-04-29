from django.urls import path
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


urlpatterns = [
    path("", EntryListView.as_view(), name="news"),
    path("blogpost/", BlogPostListView.as_view(), name="news-blogpost-list"),
    path("link/", LinkListView.as_view(), name="news-link-list"),
    path("news/", NewsListView.as_view(), name="news-news-list"),
    path("poll/", PollListView.as_view(), name="news-poll-list"),
    path("video/", VideoListView.as_view(), name="news-video-list"),
    path("add/", AllTypesCreateView.as_view(), name="news-create"),
    path("add/news/", NewsCreateView.as_view(), name="news-news-create"),
    path(
        "add/blogpost/",
        BlogPostCreateView.as_view(),
        name="news-blogpost-create",
    ),
    path("add/link/", LinkCreateView.as_view(), name="news-link-create"),
    path("add/poll/", PollCreateView.as_view(), name="news-poll-create"),
    path("add/video/", VideoCreateView.as_view(), name="news-video-create"),
    path("moderate/", EntryModerationListView.as_view(), name="news-moderate"),
    path(
        "moderate/<slug:slug>/",
        EntryModerationDetailView.as_view(),
        name="news-moderate-detail",
    ),
    path(
        "moderate/magic/<str:token>/",
        EntryModerationMagicApproveView.as_view(),
        name="news-magic-approve",
    ),
    path("entry/<slug:slug>/", EntryDetailView.as_view(), name="news-detail"),
    path(
        "entry/<slug:slug>/approve/",
        EntryApproveView.as_view(),
        name="news-approve",
    ),
    path(
        "entry/<slug:slug>/delete/",
        EntryDeleteView.as_view(),
        name="news-delete",
    ),
    path(
        "entry/<slug:slug>/update/",
        EntryUpdateView.as_view(),
        name="news-update",
    ),
]
