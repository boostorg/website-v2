from django.urls import path

from feedback.views import FeedbackTokenView, FeedbackView

urlpatterns = [
    path("", FeedbackView.as_view(), name="feedback"),
    path("token/", FeedbackTokenView.as_view(), name="feedback-token"),
]
