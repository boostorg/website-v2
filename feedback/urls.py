from django.urls import path

from feedback.views import FeedbackView

urlpatterns = [
    path("", FeedbackView.as_view(), name="feedback"),
]
