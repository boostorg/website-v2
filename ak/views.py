import requests
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.views import View
from django.views.generic import TemplateView

from config.settings import JDOODLE_API_CLIENT_ID, JDOODLE_API_CLIENT_SECRET
from libraries.models import Category, Library
from news.models import Entry
from versions.models import Version


class HomepageView(TemplateView):
    """
    Our default homepage for temp-site.  We expect you to not use this view
    after you start working on your project.
    """

    template_name = "homepage.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["entries"] = Entry.objects.published().order_by("-publish_at")[:3]
        latest_version = Version.objects.most_recent()
        context["latest_version"] = latest_version
        context["featured_library"] = self.get_featured_library(latest_version)
        return context

    def get_featured_library(self, latest_version):
        library = Library.objects.filter(featured=True).first()

        # If we don't have a featured library, return a random library
        if not library:
            library = (
                Library.objects.filter(library_version__version=latest_version)
                .order_by("?")
                .first()
            )

        return library


class HomepageBetaView(TemplateView):
    """
    Boost homepage
    """

    template_name = "homepage_beta.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        libraries, categories = [], []
        if "category" in self.request.GET and self.request.GET["category"] != "":
            context["category"] = Category.objects.get(
                slug=self.request.GET["category"]
            )
            libraries = Library.objects.filter(categories=context["category"]).order_by(
                "name"
            )
        else:
            context["category"] = None
            libraries = Library.objects.all().order_by("name")
            categories = Category.objects.all().order_by("name")
        if "version" in self.request.GET:
            context["version"] = Version.objects.filter(
                slug=self.request.GET["version"]
            ).first()
        else:
            context["version"] = Version.objects.most_recent()
        if "library" in self.request.GET:
            context["library"] = Library.objects.filter(
                slug=self.request.GET["library"]
            ).first()
            categories = context["library"].categories.order_by("name")
            if "category" in self.request.GET and self.request.GET["category"] != "":
                context["category"] = categories.filter(
                    slug=self.request.GET["category"]
                ).first()
                libraries = (
                    Library.objects.filter(categories__in=categories)
                    .order_by("name")
                    .all()
                )
        else:
            context["library"] = (
                libraries[0] if libraries else Library.objects.order_by("name").first()
            )
            if "category" in self.request.GET and self.request.GET["category"] != "":
                context["category"] = categories.filter(
                    slug=self.request.GET["category"]
                ).first()

        context["versions"] = Version.objects.active().order_by("-release_date")
        context["libraries"] = libraries
        context["categories"] = categories

        context["entries"] = Entry.objects.published().order_by("-publish_at")[:2]
        return context

    def post(self, request, *args, **kwargs):
        code = request.POST.get("code", "")
        if not code:
            return render(request, self.template_name)
        api_url = "https://api.jdoodle.com/v1/execute"
        data = {
            "clientId": JDOODLE_API_CLIENT_ID,
            "clientSecret": JDOODLE_API_CLIENT_SECRET,
            "script": code,
            "language": "cpp",
            "versionIndex": "3",
        }
        response = requests.post(api_url, json=data)
        result = response.json()
        output = result.get("output", "")
        error = result.get("error", "")
        return render(request, self.template_name, {"output": output, "error": error})


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
