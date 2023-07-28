from django.views.generic import TemplateView


class SupportView(TemplateView):
    """
    Generic base view for the support view
    """

    template_name = "support/support.html"
