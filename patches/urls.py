from django.urls import path

from patches.views import PatchDetailView
from patches.views import PatchListView

app_name = "patches"
urlpatterns = [
    path("", PatchListView.as_view(), name="list-view"),
    # Note that this is made generic to match legacy links which are in the form of boost.org/patches/{Major.Minor.Patch}/{Patch Name}
    path(
        "<str:version_slug>/<str:patch_name>/",
        PatchDetailView.as_view(),
        name="detail-view",
    ),
]
