import structlog
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.views import View
from django.views.generic import TemplateView

from core.calendar import extract_calendar_events, events_by_month, get_calendar
from libraries.constants import LATEST_RELEASE_URL_PATH_STR
from libraries.models import Library
from news.models import Entry
from versions.models import Version


logger = structlog.get_logger()


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
        context["events"] = self.get_events()
        if context["events"]:
            context["num_months"] = len(context["events"])
        else:
            context["num_months"] = 0
        context["LATEST_RELEASE_URL_PATH_STR"] = LATEST_RELEASE_URL_PATH_STR
        return context

    def get_events(self):
        """Returns the events from the Boost Google Calendar."""
        cached_events = cache.get(settings.EVENTS_CACHE_KEY)
        if cached_events:
            return cached_events

        try:
            raw_event_data = get_calendar()
        except Exception:
            logger.info("Error getting events")
            return

        if not raw_event_data:
            return

        events = extract_calendar_events(raw_event_data)
        sorted_events = events_by_month(events)
        cache.set(
            settings.EVENTS_CACHE_KEY,
            dict(sorted_events),
            settings.EVENTS_CACHE_TIMEOUT,
        )

        return dict(sorted_events)

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


def custom_404_view(request, exception=None):
    return render(request, "404.html", status=404)


class OKView(View):
    def get(self, *args, **kwargs):
        return HttpResponse("200 OK", status=200)
