from django.urls import path

from donations.views import DonationThankYouView

urlpatterns = [path("<uuid:slug>/", DonationThankYouView.as_view(), name="thank_you")]
