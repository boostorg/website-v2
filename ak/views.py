import structlog
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.views import View
from django.views.generic import TemplateView

from core.calendar import (
    extract_calendar_events,
    events_by_month,
    get_calendar,
    upcoming_events,
)
from core.install_commands import INSTALL_PKG_MANAGERS, INSTALL_SYSTEM_INSTALL
from core.mixins import V3Mixin
from libraries.constants import LATEST_RELEASE_URL_PATH_STR
from libraries.mixins import ContributorMixin
from news.models import Entry
from testimonials.models import Testimonial
from ak.homepage import (
    WHY_BOOST_CARDS,
    build_community_posts,
    build_get_started_code,
    build_join_developers_links,
    build_library_intro,
    hero_image_context,
)
from testimonials.utils import get_testimonial_cards
from libraries.utils import commit_data_to_stats_bars, get_commit_data_by_release

logger = structlog.get_logger()


class HomepageView(V3Mixin, ContributorMixin, TemplateView):
    """
    Define all the pieces that will be displayed on the home page
    """

    template_name = "homepage.html"

    v3_template_name = "v3/homepage.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["entries"] = Entry.objects.published().order_by("-publish_at")[:3]
        context["events"] = self.get_events()
        testimonials = (
            Testimonial.objects.live()
            .filter(pull_quote__gt="")
            .order_by("-first_published_at")
        )
        context["testimonials"] = testimonials
        context["num_testimonials"] = testimonials.count()
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

    def get_v3_context_data(self, **kwargs):
        # super() here is TemplateView.get_context_data, not this view's
        # legacy get_context_data — V3Mixin merges the legacy context in
        # via render_v3_response.
        ctx = super().get_context_data(**kwargs)

        # Install Card
        ctx["install_card_pkg_managers"] = INSTALL_PKG_MANAGERS
        ctx["install_card_system_install"] = INSTALL_SYSTEM_INSTALL

        # Why Boost Card 
        ctx["why_boost_cards"] = WHY_BOOST_CARDS

        # Posts Card
        ctx["community_posts"] = build_community_posts()

        # Join Card
        ctx["join_developers_links"] = build_join_developers_links()

        # Upcoming Events
        ctx["upcoming_events"] = upcoming_events(self.get_events(), 4)
        
        # Testimonial Card
        ctx["testimonial_cards"] = get_testimonial_cards(limit=5)
        
        # Get Started Card
        ctx["get_started_code"] = build_get_started_code()

        # Library Intro Card
        ctx["library_intro"] = build_library_intro()
        
        # "Boost in numbers" is project-wide, not tied to the featured library.
        ctx["commits_data"] = commit_data_to_stats_bars(
            get_commit_data_by_release(limit=10)
        )
        
        # Hero Image
        ctx.update(hero_image_context())
        
        return ctx


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
