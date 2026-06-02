import structlog
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView

from core.constants import SLACK_MEMBER_COUNT
from core.calendar import extract_calendar_events, events_by_month, get_calendar
from core.mixins import V3Mixin
from libraries.constants import LATEST_RELEASE_URL_PATH_STR
from libraries.mixins import ContributorMixin
from news.models import Entry
from testimonials.models import Testimonial
from ak.homepage import (
    get_v3_featured_library,
    posts_for_homepage,
    upcoming_events,
)
from testimonials.utils import get_testimonial_cards
from core.mock_data import SharedResources
from libraries.utils import (
    build_library_intro_context,
    commit_data_to_stats_bars,
    get_commit_data_by_release,
    get_library_code_snippet,
)

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

        ctx["why_boost_cards"] = [
            {
                "title": "Performant",
                "description": "Optimized for production at any scale, Boost outperforms many standard benchmarks.",
                "icon_name": "speed-fast",
                "icon_viewbox": "0 0 16 16",
            },
            {
                "title": "Peer-reviewed",
                "description": "Well tested by members of the C++ standards committee.",
                "icon_name": "eye",
            },
            {
                "title": "Portable",
                "description": "Works across all platforms, compilers, and C++ standards.",
                "icon_name": "arrows-horizontal",
                "icon_viewbox": "0 0 16 16",
            },
            {
                "title": "Free",
                "description": "Open source now and always, thanks to the Boost Software License.",
                "icon_name": "lock",
                "icon_viewbox": "0 0 16 16",
            },
            {
                "title": "Innovative",
                "description": "Over 40 Boost libraries have become part of the C++ standard over the past 25 years.",
                "icon_name": "bookmarks",
                "icon_viewbox": "0 0 16 16",
            },
            {
                "title": "Community-powered",
                "description": "Contributing to Boost builds credibility, sharpens skills, and advances careers.",
                "icon_name": "users",
                "icon_viewbox": "0 0 16 16",
            },
            {
                "title": "Known worldwide",
                "description": "Used in countless projects, you've probably encountered Boost without realizing it",
                "icon_name": "building-community",
                "icon_viewbox": "0 0 16 16",
            },
            {
                "title": "Production-ready",
                "description": "Battle-tested in critical systems across industries around the globe.",
                "icon_name": "zap",
                "icon_viewbox": "0 0 16 16",
            },
        ]

        tag_display = {"blogpost": "Blog"}
        popular_entries = (
            Entry.objects.ranked()
            .filter(deleted_at__isnull=True, published=True)
            .select_related("author")[:5]
        )
        ctx["posts_from_the_boost_community"] = {
            "heading": "Posts from the Boost Community",
            "primary_cta_label": "View all posts",
            "primary_cta_url": reverse("news"),
            "variant": "card",
            "theme": "teal",
            "items": [
                {
                    "title": entry.title,
                    "url": entry.get_absolute_url(),
                    "date": entry.publish_at,
                    "category": (
                        tag_display.get(str(entry.tag).lower(), entry.tag.capitalize())
                        if entry.tag
                        else ""
                    ),
                    "tag": "",
                    "author": entry.author.to_v3_profile_dict(),
                }
                for entry in popular_entries
            ],
        }
        community_url = reverse("community")
        ctx["join_developers_building_the_future_of_cpp"] = {
            "items": [
                {
                    "title": "Get help",
                    "description": f"Tap into quick answers, networking, and chat with {SLACK_MEMBER_COUNT} members.",
                    "icon_name": "message",
                    "icon_viewbox": "0 0 16 16",
                    "url": community_url,
                },
                {
                    "title": "Contribute",
                    "description": "Learn how to test or evaluate library submissions, or submit your own.",
                    "icon_name": "documentation",
                    "icon_viewbox": "0 0 16 16",
                    "url": community_url,
                },
                {
                    "title": "Stay updated",
                    "description": "Get updates on the latest releases, fixes and announcements.",
                    "icon_name": "bullseye-pixel",
                    "url": community_url,
                },
            ]
        }
        ctx["popular_terms"] = SharedResources.popular_terms
        ctx["upcoming_events"] = upcoming_events(self.get_events(), 4)
        ctx["testimonial_data"] = {"testimonials": get_testimonial_cards(limit=5)}

        # TODO: design a proper empty state for the Get Started card. For now it
        # falls back to a static hello-world sample when the featured library
        # has no code snippet.
        ctx["get_started_code"] = {
            "heading": "Get started with our libraries",
            "code": SharedResources.code_demo_hello,
            "language": "cpp",
            "library_slug": "",
        }

        featured_library = get_v3_featured_library()
        if featured_library:
            library = featured_library.library
            ctx["library_intro"] = build_library_intro_context(
                featured_library, include_contributors=False
            )
            # Get Started code sample, tied to the featured library.
            snippet = get_library_code_snippet(library)
            if snippet:
                ctx["get_started_code"] = {
                    "heading": f"Get started with {library.display_name}",
                    "code": snippet.code,
                    "language": "cpp",
                    "library_slug": library.slug,
                }

        # "Boost in numbers" is project-wide, not tied to the featured library.
        ctx["stats_in_numbers"] = {
            "bars": commit_data_to_stats_bars(get_commit_data_by_release(limit=10))
        }

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
