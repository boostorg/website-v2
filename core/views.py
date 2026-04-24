import os
import re

import requests
from django.utils import timezone

from textwrap import dedent
from urllib.parse import urljoin
from waffle import flag_is_active

import structlog
from bs4 import BeautifulSoup
import chardet
from dateutil.parser import parse
from django.conf import settings
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.cache import caches
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseNotFound,
    HttpResponseRedirect,
    HttpRequest,
)
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.generic import TemplateView

from config.settings import ENABLE_DB_CACHE
from libraries.constants import LATEST_RELEASE_URL_PATH_STR
from libraries.mixins import VersionAlertMixin
from libraries.utils import (
    legacy_path_transform,
    generate_canonical_library_uri,
    get_prioritized_library_view,
    get_prioritized_version,
    set_selected_boost_version,
    modernize_boost_slug,
)
from versions.models import Version, docs_path_to_boost_name

from .mixins import V3Mixin
from .asciidoc import convert_adoc_to_html
from .boostrenderer import (
    convert_img_paths,
    extract_file_data,
    get_content_from_s3,
    get_meta_redirect_from_html,
    get_s3_client,
)
from .constants import (
    SourceDocType,
    BOOST_LIB_PATH_RE,
    BOOST_VERSION_REGEX,
    STATIC_CONTENT_EARLY_EXIT_PATH_PREFIXES,
)
from .htmlhelper import (
    modernize_legacy_page,
    convert_name_to_id,
    modernize_preprocessor_docs,
    remove_library_boostlook,
    is_in_no_process_libs,
    is_in_fully_modernized_libs,
    is_in_no_wrapper_libs,
    is_managed_content_type,
    is_valid_modernize_value,
    get_is_iframe_destination,
    remove_unwanted,
    minimize_uris,
    add_canonical_link,
)
from .markdown import process_md
from .models import RenderedContent, SiteSettings
from .tasks import (
    clear_rendered_content_cache_by_cache_key,
    clear_rendered_content_cache_by_content_type,
    refresh_content_from_s3,
    save_rendered_content,
)

from libraries.models import Library, LibraryVersion
from libraries.utils import (
    build_library_intro_context,
    get_commit_data_by_release_for_library,
    commit_data_to_stats_bars,
)

from .mock_data import SharedResources  # noqa: F401

logger = structlog.get_logger()


def BSLView(request):
    file_path = os.path.join(settings.BASE_DIR, "static/license.txt")

    if os.path.exists(file_path):
        with open(file_path, "r") as file:
            content = file.read()
        return HttpResponse(content, content_type="text/plain")
    else:
        raise Http404("File not found.")


class CalendarView(V3Mixin, TemplateView):
    template_name = "calendar.html"
    v3_template_name = "v3/calendar.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["boost_calendar"] = settings.BOOST_CALENDAR
        return ctx

    def get_v3_context_data(self, **kwargs):
        ctx = super().get_v3_context_data(**kwargs)
        print(self.request.headers)
        ctx["timezone"] = "America/Chicago"
        return ctx


class BoostDevelopmentView(CalendarView):
    template_name = "boost_development.html"


class ClearCacheView(UserPassesTestMixin, View):
    http_method_names = ["get"]
    login_url = "/login/"

    def get(self, request, *args, **kwargs):
        """Clears the redis and database cache for given parameters.

        Params (must pass one):
            content_type: The content type to clear. Example: "text/asciidoc"
            cache_key: The cache key to clear.
        """
        content_type = self.request.GET.get("content_type")
        cache_key = self.request.GET.get("cache_key")
        if not content_type and not cache_key:
            return HttpResponseNotFound()

        if content_type:
            clear_rendered_content_cache_by_content_type.delay(content_type)

        if cache_key:
            clear_rendered_content_cache_by_cache_key.delay(cache_key)

        return HttpResponse("Cache cleared")

    def handle_no_permission(self):
        """Handle a user without permission to access this page."""
        return HttpResponse(
            "You do not have permission to access this page.", status=403
        )

    def test_func(self):
        """Check if the user is a staff member"""
        return self.request.user.is_staff


class MarkdownTemplateView(TemplateView):
    template_name = "markdown_template.html"
    content_dir = settings.BASE_CONTENT
    markdown_local = None

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.markdown_local = kwargs.get("markdown_local", None)

    def build_path(self):
        """
        Builds the path from URL kwargs
        """
        content_path = self.kwargs.get("content_path")
        updated_legacy_path = legacy_path_transform(content_path)
        if updated_legacy_path != content_path:
            return redirect(
                reverse(
                    self.request.resolver_match.view_name,
                    kwargs={"content_path": updated_legacy_path},
                )
            )

        print(self.markdown_local)
        if self.markdown_local:
            # Can we find a file with this path?
            path = (
                f"{settings.TEMPLATES[0]['DIRS'][0]}/markdown/{self.markdown_local}.md"
            )
            if os.path.isfile(path):
                return path

        if not content_path:
            return

        # If the request includes the file extension, return that
        if content_path[-5:] == ".html" or content_path[-3:] == ".md":
            return f"{self.content_dir}/{content_path}"

        # Trim any trailing slashes
        if content_path[-1] == "/":
            content_path = content_path[:-1]

        # Can we find a markdown file with this path?
        path = f"{self.content_dir}/{content_path}.md"

        # Note: The get() method also checks isfile(), but since we need to try multiple
        # paths/extensions, we need to call it here as well.
        if os.path.isfile(path):
            return path

        # Can we find an HTML file with this path?
        path = f"{self.content_dir}/{content_path}.html"
        if os.path.isfile(path):
            return path

        # Can we find an index file with this path?
        path = f"{self.content_dir}/{content_path}/index.html"
        if os.path.isfile(path):
            return path

        # If we get here, there is nothing else for us to try.
        return

    def get(self, request, *args, **kwargs):
        """
        Verifies the file and returns the frontmatter and content
        """
        path = self.build_path()

        # Avoids a TypeError from os.path.isfile if there is no path
        if not path:
            logger.info(
                "markdown_template_view_no_valid_path",
                content_path=kwargs.get("content_path"),
                status_code=404,
            )
            raise Http404("Markdown not found")

        if not os.path.isfile(path):
            logger.info(
                "markdown_template_view_no_valid_file",
                content_path=kwargs.get("content_path"),
                path=path,
                status_code=404,
            )
            raise Http404("Post not found")

        context = {}
        context["frontmatter"], context["content"] = process_md(path)
        logger.info(
            "markdown_template_view_success",
            content_path=kwargs.get("content_path"),
            path=path,
            status_code=200,
        )
        return self.render_to_response(context)


class TermsOfUseView(V3Mixin, MarkdownTemplateView):
    """Renders the v3 Terms of Use page when the v3 flag is active, else markdown template."""

    v3_template_name = "v3/terms_of_use.html"

    def get_v3_context_data(self, **kwargs):
        return {"last_updated": "2024-02-22"}


class PrivacyPolicyView(V3Mixin, MarkdownTemplateView):
    """Renders the v3 Privacy Policy page when the v3 flag is active, else markdown template."""

    v3_template_name = "v3/privacy_policy.html"

    def get_v3_context_data(self, **kwargs):
        return {"last_updated": "2024-02-17"}


class LearnPageView(V3Mixin, TemplateView):
    v3_template_name = "v3/learn_page.html"

    def dispatch(self, request, *args, **kwargs):
        if not flag_is_active(request, "v3"):
            return HttpResponseNotFound()
        return super().dispatch(request, *args, **kwargs)

    def get_v3_context_data(self, **kwargs):
        ctx = self.get_context_data(**kwargs)
        ctx["learn_card_data"] = [
            {
                "title": "I want to learn:",
                "text": "How to install Boost, use its libraries, build projects, and get help when you need it.",
                "links": [
                    {
                        "label": "Explore common use cases",
                        "url": "https://www.example.com",
                    },
                    {"label": "Build with CMake", "url": "https://www.example.com"},
                    {"label": "Visit the FAQ", "url": "https://www.example.com"},
                ],
                "url": "https://www.example.com",
                "label": "Learn more about Boost",
                "image_src": f"{ settings.STATIC_URL }/img/v3/examples/Learn_Card_Image.png",
                "mobile_image_src": f"{ settings.STATIC_URL }/img/v3/examples/Cheetah_Mobile.png",
            },
            {
                "title": "I want to learn:",
                "text": "How to install Boost, use its libraries, build projects, and get help when you need it.",
                "links": [
                    {
                        "label": "Explore common use cases",
                        "url": "https://www.example.com",
                    },
                    {"label": "Build with CMake", "url": "https://www.example.com"},
                    {"label": "Visit the FAQ", "url": "https://www.example.com"},
                ],
                "url": "https://www.example.com",
                "label": "Learn more about Boost",
                "image_src": f"{ settings.STATIC_URL}img/v3/examples/Learn_Octopus.png",
                "mobile_image_src": f"{ settings.STATIC_URL }/img/v3/examples/Octopus_Mobile.png",
            },
        ]

        demo_cards = [
            {
                "title": "Get help",
                "description": "Tap into quick answers, networking, and chat with 24,000+ members.",
                "cta_label": "Start here",
                "cta_href": reverse("community"),
            },
            {
                "title": "Documentation",
                "description": "Browse library docs, examples, and release notes in one place.",
                "cta_label": "View docs",
                "cta_href": reverse("docs"),
            },
            {
                "title": "Community",
                "description": "Mailing lists, GitHub, and community guidelines for contributors.",
                "cta_label": "Join",
                "cta_href": reverse("community"),
            },
            {
                "title": "Releases",
                "description": "Latest releases, download links, and release notes.",
                "cta_label": "Download",
                "cta_href": reverse("releases-most-recent"),
            },
            {
                "title": "Libraries",
                "description": "Explore the full catalog of Boost C++ libraries with docs and metadata.",
                "cta_label": "Browse libraries",
                "cta_href": reverse("libraries"),
            },
            {
                "title": "News",
                "description": "Blog posts, announcements, and community news from the Boost project.",
                "cta_label": "Read news",
                "cta_href": reverse("news"),
            },
            {
                "title": "Getting started",
                "description": "Step-by-step guides to build and use Boost in your projects.",
                "cta_label": "Get started",
                "cta_href": reverse("getting-started"),
            },
            {
                "title": "Resources",
                "description": "Learning resources, books, and other materials for Boost users.",
                "cta_label": "View resources",
                "cta_href": reverse("resources"),
            },
            {
                "title": "Calendar",
                "description": "Community events, meetings, and review schedule.",
                "cta_label": "View calendar",
                "cta_href": reverse("calendar"),
            },
            {
                "title": "Donate",
                "description": "Support the Boost Software Foundation and open-source C++.",
                "cta_label": "Donate",
                "cta_href": reverse("donate"),
            },
        ]

        ctx["library_cards"] = demo_cards
        ctx["why_boost_cards"] = demo_cards[:6]
        ctx["calendar_card"] = {
            "title": "Boost is released three times a year",
            "text": "Each release has updates to existing libraries, and any new libraries that have passed the rigorous acceptance process.",
            "primary_button_url": "www.example.com",
            "primary_button_label": "View the Release Calendar",
            "secondary_button_url": "www.example.com",
            "secondary_button_label": "Secondary Button",
            "image": f"{ settings.STATIC_URL }/img/v3/demo_page/Calendar.png",
        }
        ctx["info_card"] = {
            "title": "How we got here",
            "text": "Since 1998, Boost has been where C++ innovation happens. What started with three developers has grown into the foundation of modern C++ development.",
            "primary_button_url": "www.example.com",
            "primary_button_label": "Explore Our History",
        }
        ctx["post_cards_data"] = {
            "heading": "Posts from the Boost Community",
            "view_all_url": "#",
            "view_all_label": "View All Posts",
            "variant": "Content Card",
            "posts": 4
            * [
                {
                    "title": "A talk by Richard Thomson at the Utah C++ Programmers Group",
                    "url": "#",
                    "description": "Lorem Ispum Sum Delores",
                    "date": "03/03/2025",
                    "category": "Issues",
                    "tag": "beast",
                    "author": {
                        "name": "Richard Thomson",
                        "role": "Contributor",
                        "show_badge": True,
                        "avatar_url": "/static/img/v3/demo_page/Avatar.png",
                    },
                }
            ],
        }
        ctx["boost_community_data"] = {
            "heading": "The Boost community",
            "view_all_url": "#",
            "view_all_label": "Explore the community",
            "posts": 3
            * [
                {
                    "title": "A talk by Richard Thomson at the Utah C++ Programmers Group",
                    "description": "Lorem Ispum Sum Delores",
                    "url": "#",
                    "date": "03/03/2025",
                    "category": "Issues",
                    "tag": "beast",
                    "author": {
                        "name": "Richard Thomson",
                        "role": "Contributor",
                        "show_badge": True,
                        "avatar_url": "/static/img/v3/demo_page/Avatar.png",
                    },
                }
            ],
        }
        return ctx


class ContentNotFoundException(Exception):
    pass


class BaseStaticContentTemplateView(TemplateView):
    template_name = "adoc_content.html"
    allowed_db_save_types = {"text/asciidoc"}
    html_content_types = {"text/html", "text/html; charset=utf-8"}

    def get(self, request, *args, **kwargs):
        """Return static content that originates in S3.

        The result is cached in a couple of different places to avoid multiple
        roundtrips to S3.

        Any valid S3 key to the S3 bucket specified in settings can be returned by
        this view. Pages like the Help page are stored in S3 and rendered via
        this view, for example.

        See the *_static_config.json files for URL mappings to specific S3 keys.
        """
        content_path = self.kwargs.get("content_path")

        # Exit early for paths we know we don't want to handle here. We know that these
        #  paths should have been resolved earlier by the URL router, and if we return
        #  a 404 here redirecting will be handled by the webserver configuration.
        if content_path.startswith(STATIC_CONTENT_EARLY_EXIT_PATH_PREFIXES):
            raise Http404("Content not found")

        updated_legacy_path = legacy_path_transform(content_path)
        if updated_legacy_path != content_path:
            return redirect(
                reverse(
                    self.request.resolver_match.view_name,
                    kwargs={"content_path": updated_legacy_path},
                )
            )

        # For some reason, if a user cancels a social signup (cancelling a GitHub
        # signup, for example), the redirect URL comes through this view, so we
        # must manually redirect it.
        if "accounts/github/login/callback" in content_path:
            return redirect(content_path)

        try:
            content_path = self.get_library_content_path(content_path)
            self.content_dict = self.get_content(content_path)
            # If the content is an HTML file with a meta redirect, redirect the user.
            if self.content_dict.get("redirect"):
                return redirect(self.content_dict.get("redirect"))

        except ContentNotFoundException:
            logger.info(f"get_content_from_s3_view_not_in_cache {content_path} 404")
            raise Http404("Content not found")
        return super().get(request, *args, **kwargs)

    def get_library_content_path(self, content_path):
        # here we handle the translation from "release/..." to /$version_x_y_z/...
        if content_path.startswith(f"{LATEST_RELEASE_URL_PATH_STR}/"):
            version = Version.objects.most_recent()
            content_path = content_path.replace(
                f"{LATEST_RELEASE_URL_PATH_STR}/", f"{version.stripped_boost_url_slug}/"
            )
        return content_path

    def cache_result(self, static_content_cache, cache_key, result):
        static_content_cache.set(cache_key, result)

    def get_content(self, content_path):
        """Return content from cache, database, or S3."""
        static_content_cache = caches["static_content"]
        cache_key = f"static_content_{content_path}"
        result = self.get_from_cache(static_content_cache, cache_key)

        if result is None:
            result = self.get_from_database(cache_key)
            if result:
                # When we get a result from the database, we refresh its content
                refresh_content_from_s3.delay(content_path, cache_key)

        if result is None:
            result = self.get_from_s3(content_path)
            if result:
                # Save to database
                self.save_to_database(cache_key, result)
                # Cache the result
                self.cache_result(static_content_cache, cache_key, result)

        if result is None:
            logger.info(
                "get_content_from_s3_view_no_valid_object",
                key=content_path,
                status_code=404,
            )
            raise ContentNotFoundException("Content not found")

        return result

    def get_context_data(self, **kwargs):
        """Return the content and content type for the template.

        In some cases, the content type is changed depending on the context.

        """
        context = super().get_context_data(**kwargs)
        content_type = self.content_dict.get("content_type")
        content = self.content_dict.get("content")

        if content_type == "text/asciidoc":
            content_type = "text/html"

        context.update(
            {
                "content": content,
                "content_type": content_type,
                "selected_version": self.get_selected_version(),
            }
        )
        logger.info(
            "get_content_from_s3_view_success", key=self.kwargs.get("content_path")
        )

        return context

    def get_selected_version(self) -> Version | None:
        content_path = self.kwargs.get("content_path")
        boost_name = docs_path_to_boost_name(content_path)
        if not boost_name:
            return None
        try:
            version = Version.objects.get(name=boost_name)
        except Version.DoesNotExist:
            version = None
        return version

    def get_from_cache(self, static_content_cache, cache_key):
        cached_result = static_content_cache.get(cache_key)
        return cached_result if cached_result else None

    def get_from_database(self, cache_key) -> dict[str, str | bytes] | None:
        rendered_content_cache_time = 2628288
        dev_docs = ["static_content_develop/", "static_content_master/"]
        for substring in dev_docs:
            if substring in cache_key:
                rendered_content_cache_time = 3600
        now = timezone.now()
        start_time = now - timezone.timedelta(seconds=rendered_content_cache_time)
        try:
            content_obj = RenderedContent.objects.filter(modified__gte=start_time).get(
                cache_key=cache_key
            )
            return {
                "content": content_obj.content_html.encode("utf-8"),
                "content_type": content_obj.content_type,
                "updated": content_obj.modified,
            }
        except RenderedContent.DoesNotExist:
            return None

    def get_from_s3(self, content_path):
        result = get_content_from_s3(key=content_path)
        if not result:
            return None

        content = result.get("content")
        content_type = result.get("content_type")
        result["source_content_type"] = None

        # Check if the content is an asciidoc file. If so, convert it to HTML.
        # todo: confirm necessary: not clear where this is still needed, as the
        #  content type for library docs is set to text/html, maybe descriptions and
        #  release notes
        if content_type == "text/asciidoc":
            result["content"] = self.convert_adoc_to_html(content)

        # Check if the content is an HTML file. If so, check for a meta redirect.
        if content_type.startswith("text/html"):
            has_redirect = get_meta_redirect_from_html(content)
            if not has_redirect and "spirit-nav".encode() not in content:
                # Yes, this is a little gross, but it's the best we could think of.
                # The 'assert', 'url' libraries (1.89) are examples that set this,
                # is essentially everything that's not an antoradoc. Perfect is the
                # enemy of good enough.
                result["source_content_type"] = SourceDocType.ASCIIDOC

        return result

    def get_template_names(self):
        content_type = self.content_dict.get("content_type")
        if content_type == "text/asciidoc":
            return [self.template_name]
        return []

    def render_to_response(self, context, **response_kwargs):
        """Return the HTML response with a template, or just the content directly."""
        if self.get_template_names():
            content = self.process_content(context["content"])
            context["content"] = content
            return super().render_to_response(context, **response_kwargs)
        content = self.process_content(context["content"])
        return HttpResponse(content, content_type=context["content_type"])

    def save_to_database(self, cache_key, result):
        """Saves the rendered asciidoc content to the database."""
        content_type = result.get("content_type")
        if content_type in self.allowed_db_save_types:
            last_updated_at_raw = result.get("last_updated_at")
            last_updated_at = (
                parse(last_updated_at_raw) if last_updated_at_raw else None
            )
            save_rendered_content.delay(
                cache_key,
                content_type,
                result["content"],
                last_updated_at=last_updated_at,
            )

    def convert_adoc_to_html(self, content):
        """Renders asciidoc content to HTML."""
        return convert_adoc_to_html(content)

    def process_content(self, content):
        """No op, override in children if required."""
        return content


class StaticContentTemplateView(BaseStaticContentTemplateView):
    def get(self, request, content_path, *args, **kwargs):
        # filter out direct access to the doc paths
        path_regexes = [
            re.compile(rf"^{BOOST_VERSION_REGEX}/doc/html/.+$"),
            re.compile(rf"^{BOOST_VERSION_REGEX}/libs/.+$"),
        ]
        path_match = any(regex.match(content_path) for regex in path_regexes)
        if path_match:
            raise Http404("Content not found")
        return super().get(request, *args, **kwargs)

    def process_content(self, content):
        """Process the content we receive from S3"""
        content_html = self.content_dict.get("content")
        content_type = self.content_dict.get("content_type")
        content_key = self.content_dict.get("content_key")

        # Replace relative image paths will fully-qualified ones so they will render
        if content_type == "text/html" or content_type == "text/asciidoc":
            # Prefix the new URL path with "/images" so it routes through
            # our ImageView class
            url_parts = ["/images"]

            if content_key:
                # Get the path from the S3 key by stripping the filename from the S3 key
                directory = os.path.dirname(content_key)
                url_parts.append(directory.lstrip("/"))

            # Generate the replacement path to the image
            s3_path = "/".join(url_parts)
            # Process the HTML to replace the image paths
            content = convert_img_paths(str(content_html), s3_path)
        return content


def normalize_boost_doc_path(content_path: str) -> str:
    content_path = content_path.lstrip("boost_")
    if content_path.startswith(LATEST_RELEASE_URL_PATH_STR):
        version = Version.objects.most_recent()
        content_path = content_path.replace(
            f"{LATEST_RELEASE_URL_PATH_STR}/", f"{version.stripped_boost_url_slug}/"
        )
    # Special case for Boost.Process
    if content_path == "1_88_0/doc/html/process.html":
        content_path = "1_88_0/libs/process/doc/html/index.html"

    # Match versioned library paths
    matches = BOOST_LIB_PATH_RE.match(content_path)
    if matches:
        groups = matches.groups()
        if groups and not groups[0]:
            content_path = f"boost_{content_path}"

    return f"/archives/{content_path}"


class DocLibsTemplateView(VersionAlertMixin, BaseStaticContentTemplateView):
    allowed_db_save_types = {
        "text/asciidoc",
        "text/html",
        "text/html; charset=utf-8",
        "text/css; charset=utf-8",
    }

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        old_version_slug = self.kwargs.get("content_path").split("/", 1)[0]
        version_slug = modernize_boost_slug(old_version_slug)
        set_selected_boost_version(version_slug, response)
        return response

    def get_from_s3(self, content_path):
        legacy_url = normalize_boost_doc_path(content_path)
        return super().get_from_s3(legacy_url)

    def process_content(self, content: bytes):
        """Replace page header with the local one."""
        context = super().get_context_data()
        content_type = self.content_dict.get("content_type")
        modernize = self.request.GET.get("modernize", "med").lower()
        if (
            not is_managed_content_type(content_type)
            or not is_valid_modernize_value(modernize)
            or get_is_iframe_destination(self.request.headers)
        ):
            return content
        # everything from this point should be html
        req_uri = self.request.build_absolute_uri()
        canonical_uri = generate_canonical_library_uri(req_uri)

        soup = BeautifulSoup(content, "html.parser")

        # handle libraries that expect no processing
        if is_in_no_process_libs(self.request.path):
            soup = self._required_content_changes(soup, canonical_uri=canonical_uri)
            return str(soup)

        soup = self._required_modernization_changes(soup)

        context.update(
            {
                "content": str(soup),
                "canonical_uri": canonical_uri if canonical_uri != req_uri else None,
            }
        )
        template_name = "original_docs.html"

        if is_in_fully_modernized_libs(self.request.path):
            # prepare a fully modernized version in an iframe
            logger.info(f"fully modernized lib {self.request.path=}")
            context_update = self._fully_modernize_content(
                soup, self.establish_source_content_type(self.request.path)
            )
            context.update(context_update)
            template_name = "docsiframe.html"

        if is_in_no_wrapper_libs(self.request.path):
            context["no_wrapper"] = True

        context["content"] = self._required_content_string_changes(context["content"])

        return render_to_string(template_name, context, request=self.request)

    def establish_source_content_type(self, path: str) -> SourceDocType:
        source_content_type = self.content_dict.get("source_content_type")
        if source_content_type is None and SourceDocType.ANTORA.value in path:
            # hacky, but solves an edge case
            source_content_type = SourceDocType.ANTORA
        return source_content_type

    def get_content(self, content_path):
        """Return content from database (cache) or S3."""
        # For now at least we're only going to cache docs this way, user guides and
        #  will continue to be cached as they were

        result = None
        if ENABLE_DB_CACHE:
            cache_key = f"static_content_{content_path}"
            # check to see if in db, if not retrieve from s3 and save to db
            result = self.get_from_database(cache_key)
            if not result and (result := self.get_from_s3(content_path)):
                self.save_to_database(cache_key, result)
            if result:
                refresh_start = SiteSettings.load().rendered_content_replacement_start
                last_updated = result.get("updated", timezone.now())
                if refresh_start and last_updated < refresh_start:
                    refresh_content_from_s3.delay(
                        f"/archives/boost_{content_path}", cache_key
                    )
        elif content_data := self.get_from_s3(content_path):
            # structure is to allow for redirect/return to be handled in a unified way
            result = {
                "content": content_data.get("content"),
                "content_type": content_data.get("content_type"),
            }

        if result is None:
            logger.info(f"get_content_from_s3_view_no_valid_object {content_path=}")
            raise ContentNotFoundException("Content not found")

        if result["content_type"] in self.html_content_types:
            result["redirect"] = get_meta_redirect_from_html(result["content"])

        return result

    @staticmethod
    def _required_content_changes(
        content: BeautifulSoup, canonical_uri: str = None
    ) -> BeautifulSoup:
        """
        Processing for all html content, things that apply no matter the source
        """
        if canonical_uri:
            content = add_canonical_link(content, canonical_uri)

        return content

    @staticmethod
    def _required_content_string_changes(content: str) -> str:
        """
        String-based processing for all html content, things that apply no matter the source
        """
        content = minimize_uris(content)
        return content

    @staticmethod
    def _required_modernization_changes(content: BeautifulSoup):
        """
        Absolute base processing for libraries that have opted in to boostlook
        modernization
        """
        content = remove_unwanted(content)

        return content

    def _fully_modernize_content(
        self,
        soup: BeautifulSoup,
        source_content_type: SourceDocType,
        modernize: str = "med",
    ):
        """For libraries that have opted in to boostlook modernization"""
        context = {"disable_theme_switcher": False, "hide_footer": True}
        if source_content_type == SourceDocType.ASCIIDOC:
            # This was used but then changed to make docs look like the original files.
            # No libraries currently run this path, but keeping it because there's a
            #  possibility this changes back. There was a different parsing used, see
            #  git history.
            soup = convert_name_to_id(soup)
            soup = remove_library_boostlook(soup)
            soup.find("head").append(
                soup.new_tag("script", src=f"{settings.STATIC_URL}js/theme_handling.js")
            )
            context["content"] = soup.prettify()
        else:
            # Potentially pass version if needed for HTML modification.
            # We disable plausible to prevent redundant 'about:srcdoc' tracking,
            # tracking is covered by docsiframe.html
            base_html = render_to_string(
                "docs_libs_placeholder.html",
                {**context, **{"disable_plausible": True}},
                request=self.request,
            )
            insert_body: bool = modernize == "max"
            head_selector = (
                "head"
                if modernize in ("max", "med")
                else {"data-modernizer": "boost-legacy-docs-extra-head"}
            )
            context["content"] = modernize_legacy_page(
                soup,
                base_html,
                insert_body=insert_body,
                head_selector=head_selector,
                original_docs_type=source_content_type,
                show_footer=False,
                show_navbar=False,
            )

        context["full_width"] = True
        return context


class UserGuideTemplateView(BaseStaticContentTemplateView):
    def get_from_s3(self, content_path):
        legacy_url = f"/doc/{content_path}"
        return super().get_from_s3(legacy_url)

    def process_content(self, content):
        """Replace page header with the local one."""
        content_type = self.content_dict.get("content_type")
        modernize = self.request.GET.get("modernize", "med").lower()

        if not is_managed_content_type(content_type) or not is_valid_modernize_value(
            modernize
        ):
            # eventually check for more things, for example ensure this HTML
            # was not generate from Antora builders.
            return content

        context = {"disable_theme_switcher": False}
        # TODO: investigate if this base_html + template can be removed completely,
        #  seems unused
        base_html = render_to_string(
            "userguide_placeholder.html", context, request=self.request
        )
        insert_body = modernize == "max"
        head_selector = (
            "head"
            if modernize in ("max", "med")
            else {"data-modernizer": "boost-legacy-docs-extra-head"}
        )
        # potentially pass version if needed for HTML modification
        context["skip_use_boostbook_v2"] = True
        base_html = render_to_string(
            "docs_libs_placeholder.html", context, request=self.request
        )
        context["hide_footer"] = True
        context["full_width"] = True
        soup = BeautifulSoup(content, "html.parser")
        context["content"] = modernize_legacy_page(
            soup,
            base_html,
            insert_body=insert_body,
            head_selector=head_selector,
            original_docs_type=SourceDocType.ANTORA,
            show_footer=False,
            show_navbar=False,
        )
        return render_to_string("docsiframe.html", context, request=self.request)


class ModernizedDocsView(View):
    """Special case view for handling sub-pages of the Boost.Preprocessor docs."""

    def get(self, request, content_path):
        soup, response = self._load_and_transform_html(content_path, request)
        if response:
            return response  # Early return for non-HTML content

        self._inject_base_tag(soup, request)
        self._rewrite_links(soup, content_path)
        self._inject_script(soup)

        html = str(soup)
        return HttpResponse(html, content_type="text/html")

    def _load_and_transform_html(self, content_path, request):
        legacy_url = normalize_boost_doc_path(content_path)
        try:
            result = get_content_from_s3(key=legacy_url)
        except ContentNotFoundException:
            raise Http404("Not found")

        content = result.get("content")
        content_type = result.get("content_type", "")

        if not content:
            return None, HttpResponse(
                content or "", content_type=content_type or "text/plain"
            )

        html = content.decode(chardet.detect(content)["encoding"])

        if content_type.startswith("text/x-c"):
            soup = self._process_cpp_code(html)
            return None, HttpResponse(soup, content_type="text/plain")

        soup = BeautifulSoup(html, "html.parser")
        soup = convert_name_to_id(soup)
        soup, _ = modernize_preprocessor_docs(soup)
        return soup, None

    def _process_cpp_code(self, html):
        lines = html.strip().splitlines()
        code_block = "\n".join(lines)
        soup = BeautifulSoup("", "html.parser")
        html = soup.new_tag("html")
        head = soup.new_tag("head")
        body = soup.new_tag("body")
        code = soup.new_tag("code", **{"class": "language-cpp"})
        code.string = code_block
        pre = soup.new_tag("pre")
        pre.append(code)
        body.append(pre)
        html.append(head)
        html.append(body)
        soup.append(html)
        return soup

    def _inject_base_tag(self, soup, request):
        if soup.head and not soup.head.find("base"):
            base_path = request.path.rsplit("/", 1)[0] + "/"
            base_href = urljoin(request.build_absolute_uri("/"), base_path.lstrip("/"))
            if not settings.LOCAL_DEVELOPMENT:
                # Slightly hacky, but it's tricky to get this right inside the iframe
                base_href = base_href.replace("http://", "https://")
            base_tag = soup.new_tag("base", href=base_href)
            soup.head.insert(0, base_tag)

    def _inject_script(self, soup):
        script_tag = soup.new_tag(
            "script", src=f"{settings.STATIC_URL}js/theme_handling.js"
        )
        if soup.head:
            soup.head.append(script_tag)

    def _rewrite_links(self, soup, content_path):
        """Turn anchor tags meant to use framesets into htmx-driven links"""

        def _set_htmx_attrs(tag, _target):
            tag["hx-target"] = _target
            tag["hx-swap"] = "innerHTML show:none"

        base_content_path = content_path.rsplit("/", 1)[0] + "/"
        for a in soup.find_all("a"):
            target = a.get("target")
            href = a.get("href", "")

            if target in ("_top", "_parent"):
                new_path = urljoin(base_content_path, href)
                a["href"] = reverse("docs-libs-page", kwargs={"content_path": new_path})
                a["target"] = "_parent"
            elif target == "index":
                _set_htmx_attrs(a, "#sidebar")
            elif target == "desc":
                _set_htmx_attrs(a, "#main")
            elif not target:
                if content_path.endswith("contents.html"):
                    _set_htmx_attrs(a, "#sidebar")
                else:
                    _set_htmx_attrs(a, "#main")

            if target and a["target"] != "_parent":
                del a["target"]


class ImageView(View):
    def get(self, request, *args, **kwargs):
        # TODO: Add caching logic
        content_path = self.kwargs.get("content_path")
        updated_legacy_path = legacy_path_transform(content_path)
        if updated_legacy_path != content_path:
            return redirect(
                reverse(
                    self.request.resolver_match.view_name,
                    kwargs={"content_path": updated_legacy_path},
                )
            )

        client = get_s3_client()
        try:
            response = client.get_object(
                Bucket=settings.STATIC_CONTENT_BUCKET_NAME, Key=content_path
            )
            file_data = extract_file_data(response, content_path)
            content = file_data["content"]
            content_type = file_data["content_type"]

            return HttpResponse(content, content_type=content_type)
        except ContentNotFoundException:
            raise Http404("Content not found")


class BaseRedirectView(View):
    """Base view for redirecting to the latest version of a library."""

    @staticmethod
    def get_latest_library_version():
        """Return the latest version for a given library."""
        return Version.objects.most_recent().stripped_boost_url_slug


class RedirectToDocsView(BaseRedirectView):
    """View to redirect to the latest version of a library."""

    def get(self, request, libname, path):
        latest_version = self.get_latest_library_version()
        new_path = f"/doc/libs/{latest_version}/libs/{libname}/{path}"
        return HttpResponseRedirect(new_path)


class RedirectToHTMLDocsView(BaseRedirectView):
    """View to redirect to the latest version of a library.
    Supports the legacy URL structure for HTML docs.
    """

    def get(self, request, libname, path):
        latest_version = self.get_latest_library_version()
        new_path = f"/doc/libs/{latest_version}/doc/html/{libname}/{path}"
        return HttpResponseRedirect(new_path)


class RedirectToToolsView(BaseRedirectView):
    """View to redirect to the latest version of a library."""

    def get(self, request, libname):
        latest_version = self.get_latest_library_version()
        new_path = f"/doc/libs/{latest_version}/tools/{libname}/"
        return HttpResponseRedirect(new_path)


class RedirectToHTMLToolsView(BaseRedirectView):
    """View to redirect to the latest version of a library.
    Supports the legacy URL structure for tools.
    """

    def get(self, request, libname, path):
        latest_version = self.get_latest_library_version()
        new_path = f"/doc/libs/{latest_version}/tools/{libname}/{path}"
        return HttpResponseRedirect(new_path)


class RedirectToReleaseView(BaseRedirectView):
    """View to redirect to a given release page."""

    def get(self, request, requested_version):
        # Get the requested version from the path of the URL.
        requested_version = requested_version.replace("_", "-")
        requested_version = requested_version.replace("version-", "")

        new_path = f"/releases/boost-{ requested_version }/"
        return HttpResponseRedirect(new_path)


class RedirectToLibraryDetailView(BaseRedirectView):
    """View to redirect to a library's detail page"""

    def get(self, request, library_slug):
        return redirect(
            reverse(
                "library-detail",
                kwargs={
                    "library_slug": library_slug,
                    "version_slug": get_prioritized_version(request),
                },
            )
        )


class RedirectToLibrariesView(BaseRedirectView):
    """View to redirect to a versioned libraries page."""

    def get(self, request, requested_version):
        # Get the requested version from the path of the URL.
        requested_version = requested_version.replace("_", "-")

        # Handle the special case for "release" versions to redirect to the
        # most recent Boost release
        view = get_prioritized_library_view(request)
        new_path = f"/libraries/{requested_version}/{view}/"
        if requested_version == "release":
            new_path = "/libraries/"
        return HttpResponseRedirect(new_path)


@method_decorator(never_cache, name="dispatch")
class QRCodeView(View):
    """Handles QR code urls, sending them to Plausible, then redirecting to the desired url.

    QR code urls are formatted /qrc/<campaign_identifier>/desired/path/to/content/, and will
    result in a redirect to /desired/path/to/content/.

    E.g. https://www.boost.org/qrc/pv-01/library/latest/beast/ will send this full url to Plausible,
    then redirect to https://www.boost.org/library/latest/beast/
    """

    def get(self, request: HttpRequest, campaign_identifier: str, main_path: str = ""):
        absolute_url = request.build_absolute_uri(request.path)
        referrer = request.headers.get("referer", "")
        user_agent = request.headers.get("user-agent", "")

        plausible_payload = {
            "name": "pageview",
            "domain": "qrc.boost.org",
            "url": absolute_url,
            "referrer": referrer,
        }

        headers = {"Content-Type": "application/json", "User-Agent": user_agent}

        client_ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        client_ip = client_ip or request.META.get("REMOTE_ADDR")

        if client_ip:
            headers["X-Forwarded-For"] = client_ip

        try:
            requests.post(
                "https://plausible.io/api/event",
                json=plausible_payload,
                headers=headers,
                timeout=2.0,
            )
        except Exception as e:
            # Don’t interrupt the redirect - just log it
            logger.error(f"Plausible event post failed: {e}")

        # Now that we've sent the request url to plausible, we can redirect to the main_path
        # Preserve the original querystring, if any.
        # Example: /qrc/3/library/latest/algorithm/?x=1  ->  /library/latest/algorithm/?x=1
        # `main_path` is everything after qrc/<campaign>/ thanks to <path:main_path>.
        redirect_path = "/" + main_path if main_path else "/"
        qs = request.META.get("QUERY_STRING")
        if qs:
            redirect_path = f"{redirect_path}?{qs}"

        return HttpResponseRedirect(redirect_path)


class V3ComponentDemoView(TemplateView):
    """Demo page for V3 design system components."""

    template_name = "base.html"

    def get_context_data(self, **kwargs):
        from django.urls import reverse
        from libraries.utils import (
            patch_commit_authors,
        )

        CODE_DEMO_BEAST = """int main()
        {
            net::io_context ioc;
            tcp::resolver resolver(ioc);
            beast::tcp_stream stream(ioc);

            stream.connect(resolver.resolve("example.com", "80"));

            http::request<http::empty_body> req{http::verb::get, "/", 11};
            req.set(http::field::host, "example.com");

            http::write(stream, req);

            beast::flat_buffer buffer;
            http::response<http::string_body> res;
            http::read(stream, buffer, res);

            std::cout << res << std::endl;
        }"""

        CODE_DEMO_INSTALL = """brew install openssl

        export OPENSSL_ROOT=$(brew --prefix openssl)

        # Install bjam tool user config: https://www.bfgroup.xyz/b2/manual/release/index.html
        cp ./libs/beast/tools/user-config.jam $HOME"""

        context = super().get_context_data(**kwargs)
        context["code_demo_beast"] = CODE_DEMO_BEAST
        context["code_demo_hello"] = SharedResources.code_demo_hello
        context["code_demo_install"] = CODE_DEMO_INSTALL
        context["install_card_title"] = (
            "Install Boost and get started in your terminal."
        )
        context["install_card_pkg_managers"] = SharedResources.install_card_pkg_managers
        context["install_card_system_install"] = (
            SharedResources.install_card_system_install
        )
        context["popular_terms"] = SharedResources.popular_terms
        context["demo_libs"] = [
            ("asio", "Asio"),
            ("beast", "Beast"),
            ("filesystem", "Filesystem"),
            ("json", "JSON"),
            ("spirit", "Spirit"),
        ]
        context["demo_cats"] = [
            ("algorithms", "Algorithms"),
            ("containers", "Containers"),
            ("io", "I/O"),
            ("math", "Math & Numerics"),
            ("networking", "Networking"),
        ]
        context["demo_dropdown_options"] = [
            ("blog", "Blog"),
            ("link", "Link"),
            ("news", "News"),
            ("video", "Video"),
        ]
        context["demo_combo_multi_tags"] = [
            ("algorithms", "Algorithms"),
            ("containers", "Containers"),
            ("io", "I/O"),
            ("math", "Math & Numerics"),
            ("networking", "Networking"),
            ("testing", "Testing"),
            ("concurrency", "Concurrency"),
        ]
        context["badge_icons"] = [
            "badge-tier-3",
            "badge-tier-2",
            "badge-tier-1",
            "badge-tier-5",
            "badge-tier-4",
            "boost-day",
        ]
        context["demo_badges"] = [
            {
                "icon": "badge-tier-3",
                "name": "Patch Wizard",
                "earned_date": "08/08/2025",
            },
            {
                "icon": "badge-tier-5",
                "name": "Standard Bearer",
                "earned_date": "03/07/2025",
            },
            {
                "icon": "star-tier-3",
                "name": "Review Hawk",
                "earned_date": "03/06/2025",
            },
            {
                "icon": "badge-tier-2",
                "name": "Library Alchemist",
                "earned_date": "03/04/2025",
            },
            {
                "icon": "badge-tier-4",
                "name": "Bug Catcher",
                "earned_date": "02/04/2025",
            },
            {
                "icon": "badge-tier-1",
                "name": "Code Whisperer",
                "earned_date": "01/01/2025",
            },
            {
                "icon": "boost-day",
                "name": "Boost Day",
                "earned_date": "12/12/2024",
            },
        ]

        context["demo_badges_few"] = context["demo_badges"][:3]

        context["post_filter_options"] = [
            {"label": "All", "value": "all"},
            {"label": "News", "value": "news"},
            {"label": "Blog", "value": "blog"},
            {"label": "Links", "value": "links"},
            {"label": "Videos", "value": "videos"},
            {"label": "Discussions", "value": "discussions"},
            {"label": "Achievements", "value": "achievements"},
            {"label": "Issues", "value": "issues"},
        ]

        context["demo_posts"] = SharedResources.demo_posts
        context["demo_post"] = SharedResources.demo_posts[0]

        context["demo_join_community_links"] = SharedResources.demo_join_community_links

        context["demo_user_card"] = {
            "username": "vinniefalco",
            "avatar_url": "https://avatars.githubusercontent.com/u/1503976",
            "badge_name": "Bug Catcher",
            "badge": "badge-tier-3",
            "member_since": "2008",
            "role": "C++ Alliance Board Member",
            "flag_emoji": "🇺🇸",
        }

        context["button_badge_data"] = {
            "group_label": "button badges",
            "group_name": "button-badge-select",
            "badge_buttons": [
                {
                    "value": "bronze",
                    "icon": "badge-tier-1",
                    "icon_alt": "Bronze badge",
                    "checked": False,
                },
                {
                    "value": "silver",
                    "icon": "badge-tier-2",
                    "icon_alt": "Silver badge",
                    "checked": False,
                },
                {
                    "value": "gold",
                    "icon": "badge-tier-3",
                    "icon_alt": "Gold badge",
                    "checked": True,
                },
                {
                    "value": "platinum",
                    "icon": "badge-tier-5",
                    "icon_alt": "Platinum badge",
                    "checked": False,
                },
                {
                    "value": "diamond",
                    "icon": "badge-tier-4",
                    "icon_alt": "Diamond badge",
                    "checked": False,
                },
                {
                    "value": "star-tier-1",
                    "icon": "star-tier-1",
                    "icon_alt": "Bronze star",
                    "checked": False,
                },
                {
                    "value": "star-tier-2",
                    "icon": "star-tier-2",
                    "icon_alt": "Silver star",
                    "checked": False,
                },
                {
                    "value": "star-tier-3",
                    "icon": "star-tier-3",
                    "icon_alt": "Gold star",
                    "checked": False,
                },
                {
                    "value": "star-tier-5",
                    "icon": "star-tier-5",
                    "icon_alt": "Platinum star",
                    "checked": False,
                },
                {
                    "value": "star-tier-4",
                    "icon": "star-tier-4",
                    "icon_alt": "Diamond star",
                    "checked": False,
                },
                {
                    "value": "boost-day",
                    "icon": "boost-day",
                    "icon_alt": "Boost Day",
                    "checked": False,
                },
            ],
        }

        cpp_options = [
            ("all", "All"),
            ("cpp03", "C++03"),
            ("cpp11", "C++11"),
            ("cpp14", "C++14"),
            ("cpp17", "C++17"),
            ("cpp20", "C++20"),
            ("cpp23", "C++23"),
        ]
        context["library_filter_fields"] = [
            {
                "type": "dropdown",
                "name": "view",
                "label": "View",
                "options": [
                    ("list", "List"),
                    ("grid", "Grid"),
                    ("category", "Category"),
                    ("grading", "Grading"),
                ],
                "selected": "list",
                "width": "narrow",
            },
            {
                "type": "dropdown",
                "name": "grading",
                "label": "Grading",
                "options": [
                    ("all", "All"),
                    ("flagship", "Flagship"),
                    ("core", "Core"),
                    ("deprecated", "Deprecated"),
                    ("legacy", "Legacy"),
                ],
                "selected": "all",
                "width": "wide",
            },
            {
                "type": "dropdown",
                "name": "min_cpp",
                "label": "Min. C++ Version",
                "options": cpp_options,
                "selected": "all",
                "width": "narrow",
            },
            {
                "type": "dropdown",
                "name": "max_cpp",
                "label": "Max. C++ Version",
                "options": cpp_options,
                "selected": "all",
                "width": "narrow",
            },
            {
                "type": "combo_multi",
                "name": "category",
                "label": "Category",
                "options": [
                    ("algorithms", "Algorithms"),
                    ("asynchronous", "Asynchronous"),
                    ("awaitables", "Awaitables"),
                    ("containers", "Containers"),
                    ("coroutines", "Coroutines"),
                    ("correctness", "Correctness"),
                    # More dummy data to show scrollbar
                    ("data_processing", "Data processing"),
                    ("debugging", "Debugging"),
                    ("file_systems", "File systems"),
                    ("formatting", "Formatting"),
                    ("graphics", "Graphics"),
                ],
                "width": "wide",
                "placeholder": "Search",
            },
            {
                "type": "dropdown",
                "name": "sort",
                "label": "Sort by",
                "options": [
                    ("alphabetical", "Alphabetical"),
                    ("popular", "Most Popular"),
                    ("updated", "Recently Updated"),
                    ("release", "Release Date"),
                ],
                "selected": "alphabetical",
            },
        ]

        context["demo_events"] = SharedResources.demo_events

        context["demo_events_with_links"] = SharedResources.demo_events_with_links[:3]

        context["create_account_card_preview_url"] = (
            f"{settings.STATIC_URL}img/checker.png"
        )
        context["hero_background_image_url"] = (
            f"{settings.STATIC_URL}img/v3/home-page/home-page-background.png"
        )
        context["hero_legacy_image_url_light"] = (
            SharedResources.hero_legacy_image_url_light
        )
        context["hero_legacy_image_url_dark"] = (
            SharedResources.hero_legacy_image_url_dark
        )
        context["hero_image_url"] = SharedResources.hero_image_url
        context["hero_image_url_light"] = SharedResources.hero_image_url_light
        context["hero_image_url_dark"] = SharedResources.hero_image_url_dark
        context["basic_card_data"] = {
            "title": "Found a Bug?",
            "text": "We rely on developers like you to keep Boost solid. Here's how to report issues that help the whole comm",
            "primary_button_url": "www.example.com",
            "primary_button_label": "Primary Button",
            "secondary_button_url": "www.example.com",
            "secondary_button_label": "Secondary Button",
            "image": "/static/img/v3/demo_page/Calendar.png",
        }

        context["horizontal_card_data"] = SharedResources.build_anything_with_boost

        context["demo_cards_carousel_cards"] = [
            {
                "title": "Get help",
                "description": "Tap into quick answers, networking, and chat with 24,000+ members.",
                "icon_name": "info-box",
                "cta_label": "Start here",
                "cta_href": reverse("community"),
            },
            {
                "title": "Documentation",
                "description": "Browse library docs, examples, and release notes in one place.",
                "icon_name": "link",
                "cta_label": "View docs",
                "cta_href": reverse("docs"),
            },
            {
                "title": "Community",
                "description": "Mailing lists, GitHub, and community guidelines for contributors.",
                "icon_name": "human",
                "cta_label": "Join",
                "cta_href": reverse("community"),
            },
            {
                "title": "Releases",
                "description": "Latest releases, download links, and release notes.",
                "icon_name": "info-box",
                "cta_label": "Download",
                "cta_href": reverse("releases-most-recent"),
            },
            {
                "title": "Libraries",
                "description": "Explore the full catalog of Boost C++ libraries with docs and metadata.",
                "icon_name": "link",
                "cta_label": "Browse libraries",
                "cta_href": reverse("libraries"),
            },
            {
                "title": "News",
                "description": "Blog posts, announcements, and community news from the Boost project.",
                "icon_name": "device-tv",
                "cta_label": "Read news",
                "cta_href": reverse("news"),
            },
            {
                "title": "Getting started",
                "description": "Step-by-step guides to build and use Boost in your projects.",
                "icon_name": "bullseye-arrow",
                "cta_label": "Get started",
                "cta_href": reverse("getting-started"),
            },
            {
                "title": "Resources",
                "description": "Learning resources, books, and other materials for Boost users.",
                "icon_name": "get-help",
                "cta_label": "View resources",
                "cta_href": reverse("resources"),
            },
            {
                "title": "Calendar",
                "description": "Community events, meetings, and review schedule.",
                "icon_name": "info-box",
                "cta_label": "View calendar",
                "cta_href": reverse("calendar"),
            },
            {
                "title": "Donate",
                "description": "Support the Boost Software Foundation and open-source C++.",
                "icon_name": "human",
                "cta_label": "Donate",
                "cta_href": reverse("donate"),
            },
        ]

        context["learn_card_data"] = {
            "title": "I want to learn:",
            "text": "How to install Boost, use its libraries, build projects, and get help when you need it.",
            "links": [
                {"label": "Explore common use cases", "url": "https://www.example.com"},
                {"label": "Build with CMake", "url": "https://www.example.com"},
                {"label": "Visit the FAQ", "url": "https://www.example.com"},
            ],
            "url": "https://www.example.com",
            "label": "Learn more about Boost",
            "image_src": "/static/img/v3/examples/Learn Card Image.png",
        }

        context["testimonial_data"] = {
            "heading": "What Engineers are saying",
            "testimonials": SharedResources.testimonials,
        }

        context["achievements_data"] = {
            "achievements": [
                {
                    "title": "Lorem Ipsum",
                    "points": 22,
                    "description": "A longer description giving a summary of the achievement.",
                }
                for _ in range(4)
            ]
        }

        context["banner_data"] = {
            "icon_name": "alert",
            "banner_message": "This is an older version of Boost and was released in 2017. The <a href='https://www.example.com'>current version</a> is 1.90.0.",
        }

        context["account_connections_mixed"] = [
            {
                "platform": "github",
                "label": "GitHub",
                "connected": True,
                "status_text": "Connected",
                "action_label": "Manage",
                "action_url": "#",
            },
            {
                "platform": "google",
                "label": "Google",
                "connected": False,
                "status_text": "Not connected",
                "action_label": "Connect",
                "action_url": "#",
            },
        ]
        context["account_connections_all_connected"] = [
            {
                "platform": "github",
                "label": "GitHub",
                "connected": True,
                "status_text": "Connected",
                "action_label": "Manage",
                "action_url": "#",
            },
            {
                "platform": "google",
                "label": "Google",
                "connected": True,
                "status_text": "Connected",
                "action_label": "Manage",
                "action_url": "#",
            },
        ]
        context["account_connections_none_connected"] = [
            {
                "platform": "github",
                "label": "GitHub",
                "connected": False,
                "status_text": "Not connected",
                "action_label": "Connect",
                "action_url": "#",
            },
            {
                "platform": "google",
                "label": "Google",
                "connected": False,
                "status_text": "Not connected",
                "action_label": "Connect",
                "action_url": "#",
            },
        ]
        context["markdown_data"] = {
            "title": "Markdown Block",
            "markdown": dedent(
                """

            ######Insert anything Required

            * Could
            * be
            * a
            * list

            Or **bold** and *italics* and whatever it needs to be formatted or [use links](https://www.example.com)!
            """
            ),
            "button_url": "#",
            "button_label": "Optional CTA Button",
            "button_style": "primary",
        }

        context["user_profile_data"] = [
            {
                "name": "John Doe",
                "profile_url": "#",
                "role": "Author",
                "avatar_url": f"{settings.STATIC_URL}img/v3/demo_page/Avatar.png",
                "badge": "badge-tier-3",
                "bio": "",
            },
            {
                "name": "Richard Thomson",
                "profile_url": "#",
                "role": "Contributor",
                "avatar_url": "",
                "badge": "",
                "bio": "",
            },
            {
                "name": "Richard Thomson",
                "profile_url": "#",
                "role": "Contributor",
                "avatar_url": "",
                "badge": "badge-tier-1",
                "bio": "Big C++ fan. Not quite kidney-donation level, but close.",
            },
            {
                "name": "Richard Thomson",
                "profile_url": "#",
                "role": "Author",
                "avatar_url": "",
                "badge": "",
                "bio": "Big C++ fan. Not quite kidney-donation level, but close.",
            },
            {
                "name": "Peter Dimov",
                "profile_url": "#",
                "role": "Maintainer",
                "avatar_url": f"{settings.STATIC_URL}img/v3/demo_page/Avatar.png",
                "badge": "star-tier-5",
                "achievement_count": 22,
                "bio": "",
            },
            {
                "name": "Vinnie Falco",
                "profile_url": "#",
                "role": "Author",
                "avatar_url": f"{settings.STATIC_URL}img/v3/demo_page/Avatar.png",
                "badge": "boost-day",
                "achievement_count": 7,
                "bio": "Boost Day contributor.",
            },
        ]

        context["contributor_data"] = 10 * [
            {
                "name": "John Doe",
                "profile_url": "#",
                "role": "Author",
                "avatar_url": f"{settings.STATIC_URL}img/v3/demo_page/Avatar.png",
                "badge": "badge-tier-3",
                "bio": "",
            }
        ] + 10 * [
            {
                "name": "Richard Thomson",
                "profile_url": "#",
                "role": "Contributor",
                "avatar_url": "",
                "badge": "badge-tier-1",
                "bio": "",
            }
        ]

        context["release_contributor_data"] = context["contributor_data"][:8]

        latest = Version.objects.most_recent()
        if latest:
            lv = (
                LibraryVersion.objects.filter(version=latest, library__slug="beast")
                .select_related("library")
                .first()
            )
            if lv:
                context["library_intro"] = build_library_intro_context(lv)
                deps = lv.dependencies.order_by("name")
                context["dependencies_card_data"] = [
                    {
                        "name": dep.display_name_short,
                        "url": reverse(
                            "library-detail",
                            kwargs={
                                "version_slug": "latest",
                                "library_slug": dep.slug,
                            },
                        ),
                    }
                    for dep in deps
                ]

        # Commits per release: dropdown of libraries, Beast first and default
        raw_library = self.request.GET.get("library")
        library_slug = (raw_library or "beast").strip().lower()
        # Build dropdown choices: Beast first, then others alphabetically by name
        beast = Library.objects.filter(slug="beast").first()
        rest = Library.objects.exclude(slug="beast").order_by("name")[:99]
        choices = []
        if beast:
            choices.append((beast.slug, beast.display_name))
        for lib in rest:
            choices.append((lib.slug, lib.display_name))
        context["example_library_choices"] = choices

        library = Library.objects.filter(slug__iexact=library_slug).first()
        if library:
            commit_data = get_commit_data_by_release_for_library(library)
            context["example_library_commits_bars"] = commit_data_to_stats_bars(
                commit_data[-10:] if len(commit_data) > 10 else commit_data
            )
            context["example_library_name"] = library.display_name
            context["example_library_slug"] = library.slug
            context["example_library_detail_url"] = reverse(
                "library-detail",
                kwargs={
                    "version_slug": "latest",
                    "library_slug": library.slug,
                },
            )
        else:
            context["example_library_not_found"] = library_slug
            context["example_library_slug"] = library_slug

        demo_library_items = []
        demo_libs_qs = (
            Library.objects.filter(
                slug__in=[
                    "accumulators",
                    "algorithm",
                    "align",
                    "any",
                    "array",
                    "asio",
                    "assign",
                    "atomic",
                    "beast",
                    "bimap",
                    "bind",
                ]
            )
            .prefetch_related("categories", "authors")
            .order_by("name")
        )
        # Collect one author per demo library and patch CommitAuthor data
        demo_authors = {}
        for lib in demo_libs_qs:
            author = (
                lib.authors.exclude(email__startswith="deleted-")
                .exclude(github_username="")
                .first()
            ) or lib.authors.exclude(email__startswith="deleted-").first()
            if author:
                demo_authors[lib.pk] = author
        patch_commit_authors(list(demo_authors.values()))

        for lib in demo_libs_qs:
            lv = (
                LibraryVersion.objects.filter(version=latest, library=lib).first()
                if latest
                else None
            )
            cats = [
                {"label": cat.name, "url": "#", "variant": "neutral"}
                for cat in lib.categories.all()[:3]
            ]
            author = demo_authors.get(lib.pk)
            demo_library_items.append(
                {
                    "library_name": lib.display_name_short,
                    "library_url": reverse(
                        "library-detail",
                        kwargs={
                            "version_slug": "latest",
                            "library_slug": lib.slug,
                        },
                    ),
                    "description": lib.description or "",
                    "categories": cats,
                    "cpp_version": (
                        lv.get_cpp_standard_minimum_display()
                        if lv and lv.cpp_standard_minimum
                        else "C++03"
                    ),
                    "author": {
                        "name": author.display_name if author else "Unknown",
                        "role": "Contributor",
                        "avatar_url": author.get_avatar_url() if author else "",
                        "badge": "badge-tier-3",
                    },
                    "doc_url": reverse(
                        "library-detail",
                        kwargs={
                            "version_slug": "latest",
                            "library_slug": lib.slug,
                        },
                    ),
                }
            )
        context["demo_library_items"] = demo_library_items

        return context
