import structlog
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.views import View
from django.views.generic import TemplateView

from core.calendar import extract_calendar_events, events_by_month, get_calendar
from core.mixins import V3Mixin
from libraries.constants import LATEST_RELEASE_URL_PATH_STR
from libraries.mixins import ContributorMixin
from news.models import Entry
from testimonials.models import Testimonial
from core.mock_data import SharedResources


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
        ctx = super().get_context_data(**kwargs)
        ctx["install_card_pkg_managers"] = SharedResources.install_card_pkg_managers
        ctx["install_card_system_install"] = SharedResources.install_card_system_install

        demo_cards = [
            {
                "title": "Performant",
                "description": "Optimized for production at any scale, Boost outperforms many standard benchmarks.",
                "icon_name": "bullseye-arrow",
            },
            {
                "title": "Peer-reviewed",
                "description": "Well tested by members of the C++ standards committee.",
                "icon_name": "get-help",
            },
            {
                "title": "Portable",
                "description": "Works across all platforms, compilers, and C++ standards.",
                "icon_name": "link",
            },
            {
                "title": "Innovative",
                "description": "Over 40 Boost libraries have become part of the C++ standard over the past 25 years.",
                "icon_name": "bullseye-arrow",
            },
            {
                "title": "Community-powered",
                "description": "Contributing to Boost builds credibility, sharpens skills, and advances careers.",
                "icon_name": "human",
            },
            {
                "title": "Known worldwide",
                "description": "Used in countless projects, you've probably encountered Boost without realizing it.",
                "icon_name": "link",
            },
            {
                "title": "Free",
                "description": "Open source now and always, thanks to the Boost Software License.",
                "icon_name": "check",
            },
            {
                "title": "Production-ready",
                "description": "Battle-tested in critical systems across industries around the globe.",
                "icon_name": "bullseye-arrow",
            },
        ]

        ctx["library_cards"] = demo_cards
        ctx["why_boost_cards"] = demo_cards[:8]
        ctx["calendar_card"] = {
            "title": "Boost is released three times a year",
            "text": "Each release has updates to existing libraries, and any new libraries that have passed the rigorous acceptance process.",
            "primary_button_url": "www.example.com",
            "primary_button_label": "View the Release Calendar",
            "secondary_button_url": "www.example.com",
            "secondary_button_label": "Secondary Button",
            "image": f"{settings.STATIC_URL}/img/v3/demo_page/Calendar.png",
        }
        ctx["info_card"] = {
            "title": "How we got here",
            "text": "Since 1998, Boost has been where C++ innovation happens. What started with three developers has grown into the foundation of modern C++ development.",
            "primary_button_url": "www.example.com",
            "primary_button_label": "Explore Our History",
        }
        ctx["posts_from_the_boost_community"] = {
            "heading": "Posts from the Boost Community",
            "primary_cta_label": "View all posts",
            "primary_cta_url": "#",
            "variant": "card",
            "theme": "teal",
            "items": SharedResources.demo_posts[:5],
        }
        ctx["join_developers_building_the_future_of_cpp"] = {
            "items": SharedResources.demo_join_community_links[:5]
        }
        ctx["boost_community_data"] = {
            "heading": "The Boost community",
            "view_all_url": "#",
            "view_all_label": "Explore the community",
            "posts": SharedResources.demo_posts,
        }
        ctx["popular_terms"] = SharedResources.popular_terms
        ctx["demo_events_with_links"] = SharedResources.demo_events_with_links[:4]
        ctx["code_demo_hello"] = SharedResources.code_demo_hello
        ctx["stats_in_numbers"] = {
            "example_library_commits_bars": SharedResources.example_library_commits_bars
        }
        ctx["testimonial_data"] = {"testimonials": SharedResources.testimonials}

        ctx["library_intro"] = SharedResources.library_intro

        ctx["build_anything_with_boost"] = SharedResources.build_anything_with_boost

        ctx["hero_legacy_image_url_light"] = SharedResources.hero_legacy_image_url_light
        ctx["hero_legacy_image_url_dark"] = SharedResources.hero_legacy_image_url_dark
        ctx["hero_image_url"] = SharedResources.hero_image_url
        ctx["hero_image_url_light"] = SharedResources.hero_image_url_light
        ctx["hero_image_url_dark"] = SharedResources.hero_image_url_dark
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
