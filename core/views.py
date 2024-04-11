import os
import re
import structlog
from dateutil.parser import parse

from django.conf import settings
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.cache import caches
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseNotFound,
    HttpResponseRedirect,
)
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.views import View
from django.views.generic import TemplateView

from .asciidoc import process_adoc_to_html_content
from .boostrenderer import (
    get_content_from_s3,
    get_s3_client,
    extract_file_data,
    convert_img_paths,
    get_meta_redirect_from_html,
)
from .htmlhelper import modernize_legacy_page
from .markdown import process_md
from .models import RenderedContent
from .tasks import (
    clear_rendered_content_cache_by_cache_key,
    clear_rendered_content_cache_by_content_type,
    refresh_content_from_s3,
    save_rendered_content,
)

from versions.models import Version


logger = structlog.get_logger()


def BSLView(request):
    file_path = os.path.join(settings.BASE_DIR, "static/license.txt")

    if os.path.exists(file_path):
        with open(file_path, "r") as file:
            content = file.read()
        return HttpResponse(content, content_type="text/plain")
    else:
        raise Http404("File not found.")


class CalendarView(TemplateView):
    template_name = "calendar.html"

    def get(self, request, *args, **kwargs):
        context = {"boost_calendar": settings.BOOST_CALENDAR}
        return self.render_to_response(context)


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


class ContentNotFoundException(Exception):
    pass


class BaseStaticContentTemplateView(TemplateView):
    template_name = "adoc_content.html"

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

        # For some reason, if a user cancels a social signup (cancelling a GitHub
        # signup, for example), the redirect URL comes through this view, so we
        # must manually redirect it.
        if "accounts/github/login/callback" in content_path:
            return redirect(content_path)
        try:
            self.content_dict = self.get_content(content_path)
            # If the content is an HTML file with a meta redirect, redirect the user.
            if self.content_dict.get("redirect"):
                return redirect(self.content_dict.get("redirect"))

        except ContentNotFoundException:
            logger.info(
                "get_content_from_s3_view_not_in_cache",
                content_path=content_path,
                status_code=404,
            )
            raise Http404("Content not found")
        return super().get(request, *args, **kwargs)

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

        context.update({"content": content, "content_type": content_type})

        logger.info(
            "get_content_from_s3_view_success", key=self.kwargs.get("content_path")
        )

        return context

    def get_from_cache(self, static_content_cache, cache_key):
        cached_result = static_content_cache.get(cache_key)
        return cached_result if cached_result else None

    def get_from_database(self, cache_key):
        try:
            content_obj = RenderedContent.objects.get(cache_key=cache_key)
            return {
                "content": content_obj.content_html,
                "content_type": content_obj.content_type,
            }
        except RenderedContent.DoesNotExist:
            return None

    def get_from_s3(self, content_path):
        result = get_content_from_s3(key=content_path)
        if result and result.get("content"):
            content = result.get("content")
            content_type = result.get("content_type")

            # Check if the content is an asciidoc file. If so, convert it to HTML.
            if content_type == "text/asciidoc":
                result["content"] = self.convert_adoc_to_html(content)

            # Check if the content is an HTML file. If so, check for a meta redirect.
            if content_type.startswith("text/html"):
                result["redirect"] = get_meta_redirect_from_html(content)

            return result

    def get_template_names(self):
        """Return the template name."""
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
        """Saves the rendered asciidoc content to the database via celery."""
        content_type = result.get("content_type")
        last_updated_at_raw = result.get("last_updated_at")

        if content_type == "text/asciidoc":
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
        return process_adoc_to_html_content(content)

    def process_content(self, content):
        """No op, override in children if required."""
        return content


class StaticContentTemplateView(BaseStaticContentTemplateView):
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


class DocLibsTemplateView(BaseStaticContentTemplateView):
    # possible library versions are: boost_1_53_0_beta1, 1_82_0, 1_55_0b1
    boost_lib_path_re = re.compile(r"^(boost_){0,1}([0-9_]*[0-9]+[^/]*)/(.*)")
    # is_iframe_view = False

    def get_from_s3(self, content_path):
        # perform URL matching/mapping, perhaps extract the version from content_path
        matches = self.boost_lib_path_re.match(content_path)
        if matches:
            groups = matches.groups()
            if groups and not groups[0]:
                content_path = f"boost_{content_path}"

        legacy_url = f"/archives/{content_path}"
        return super().get_from_s3(legacy_url)

    def process_content(self, content):
        """Replace page header with the local one."""
        content_type = self.content_dict.get("content_type")
        # Is the request coming from an iframe? If so, let's disable the modernization.

        sec_fetch_destination = self.request.headers.get("Sec-Fetch-Dest", "")
        is_iframe_destination = sec_fetch_destination in ["iframe", "frame"]

        modernize = self.request.GET.get("modernize", "med").lower()

        if (
            ("text/html" or "text/html; charset=utf-8") not in content_type
            or modernize not in ("max", "med", "min")
            or is_iframe_destination
        ):
            # eventually check for more things, for example ensure this HTML
            # was not generate from Antora builders.
            return content

        context = {"disable_theme_switcher": False}
        base_html = render_to_string(
            "docs_libs_placeholder.html", context, request=self.request
        )
        insert_body = modernize == "max"
        head_selector = (
            "head"
            if modernize in ("max", "med")
            else {"data-modernizer": "boost-legacy-docs-extra-head"}
        )
        # potentially pass version if needed for HTML modification
        return modernize_legacy_page(
            content, base_html, insert_body=insert_body, head_selector=head_selector
        )


class UserGuideTemplateView(BaseStaticContentTemplateView):
    def get_from_s3(self, content_path):
        legacy_url = f"/doc/{content_path}"
        return super().get_from_s3(legacy_url)

    def process_content(self, content):
        """Replace page header with the local one."""
        content_type = self.content_dict.get("content_type")
        modernize = self.request.GET.get("modernize", "med").lower()
        if content_type != "text/html" or modernize not in ("max", "med", "min"):
            # eventually check for more things, for example ensure this HTML
            # was not generate from Antora builders.
            return content

        context = {"disable_theme_switcher": False}
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
        return modernize_legacy_page(
            content, base_html, insert_body=insert_body, head_selector=head_selector
        )


class ImageView(View):
    def get(self, request, *args, **kwargs):
        # TODO: Add caching logic
        content_path = self.kwargs.get("content_path")

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
