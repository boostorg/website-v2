from django.views.generic.detail import DetailView

from donations.models import CharitableDonation


class DonationThankYouView(DetailView):
    template_name = "v3/donation_thank_you.html"
    model = CharitableDonation
    slug_field = "uuid"
