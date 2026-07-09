from django.urls import path

from mailing_list.views import ConfirmSubscriptionView
from mailing_list.views import ModalSubscribeView
from mailing_list.views import PostAuthSubscribeView
from mailing_list.views import QuickSubscribeView
from mailing_list.views import SubscribeView

urlpatterns = [
    path("subscribe/", SubscribeView.as_view(), name="mailing-list-subscribe"),
    path(
        "quick-subscribe/",
        QuickSubscribeView.as_view(),
        name="mailing-list-quick-subscribe",
    ),
    path(
        "modal-subscribe/",
        ModalSubscribeView.as_view(),
        name="mailing-list-modal-subscribe",
    ),
    path(
        "post-auth-subscribe/",
        PostAuthSubscribeView.as_view(),
        name="mailing-list-post-auth-subscribe",
    ),
    path(
        "confirm/<str:token>/",
        ConfirmSubscriptionView.as_view(),
        name="mailing-list-confirm",
    ),
]
