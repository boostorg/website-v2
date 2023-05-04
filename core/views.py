import os.path
import re
import structlog

from django.conf import settings
from django.core.cache import caches
from django.http import Http404, HttpResponse, HttpResponseNotFound
from django.template.response import TemplateResponse
from django.views.generic import TemplateView, View

from .boostrenderer import get_content_from_s3
from .markdown import process_md

logger = structlog.get_logger()


class MarkdownTemplateView(TemplateView):
    template_name = "markdown_template.html"
    content_dir = settings.BASE_CONTENT

    def build_path(self):
        """
        Builds the path from URL kwargs
        """
        content_path = self.kwargs.get("content_path")

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
            raise Http404("Page not found")

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


class StaticContentTemplateView(View):
    def get(self, request, *args, **kwargs):
        """
        Verifies the file and returns the raw static content from S3
        mangling paths using the stage_static_config.json settings
        """
        content_path = kwargs.get("content_path")

        # Get the static content cache
        static_content_cache = caches["static_content"]

        # Check if the content is in the cache
        cache_key = f"static_content_{content_path}"
        cached_result = static_content_cache.get(cache_key)

        if cached_result:
            content, content_type = cached_result
        else:
            # Fetch content from S3 if not in cache
            result = get_content_from_s3(key=kwargs.get("content_path"))
            if not result:
                logger.info(
                    "get_content_from_s3_view_no_valid_object",
                    key=kwargs.get("content_path"),
                    status_code=404,
                )
                return HttpResponseNotFound("Page not found")

            content, content_type = result
            # Store the result in cache
            static_content_cache.set(
                cache_key,
                (content, content_type),
                settings.CACHES["static_content"]["TIMEOUT"],
            )

        response = HttpResponse(content, content_type=content_type)
        logger.info(
            "get_content_from_s3_view_success",
            key=kwargs.get("content_path"),
            status_code=response.status_code,
        )
        return response
