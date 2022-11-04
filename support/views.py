from django.views.generic import TemplateView
from .forms import ContactForm


class SupportBaseView(TemplateView):
    """
    Generic base view for the contact form
    used on contact and support views
    """

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = ContactForm
        return context


class SupportView(SupportBaseView):
    """
    View for the Support page with contact form
    TODO: Add reCaptcha
    """

    template_name = "support/support.html"


class ContactView(SupportBaseView):
    """
    View for the Support page with contact form
    TODO: Add reCaptcha
    """

    template_name = "support/contact.html"
