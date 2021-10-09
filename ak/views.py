from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.views import View
from django.views.generic import TemplateView


class HomepageView(TemplateView):
    """
    Our default homepage for AlphaKit.  We expect you to not use this view
    after you start working on your project.
    """

    template_name = "homepage.html"


class ForbiddenView(View):
    """
    This view raises an exception to test our 403.html template
    """

    def get(self, *args, **kwargs):
        raise PermissionDenied("403 Forbidden")


class InternalServerErrorView(View):
    """
    This view raises an exception to test our 500.html template
    """

    def get(self, *args, **kwargs):
        raise ValueError("500 Internal Server Error")


class NotFoundView(View):
    """
    This view raises an exception to test our 404.html template
    """

    def get(self, *args, **kwargs):
        raise Http404("404 Not Found")


class OKView(View):
    def get(self, *args, **kwargs):
        return HttpResponse("200 OK", status=200)
