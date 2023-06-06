import os.path
import structlog
import tempfile

from django.conf import settings
from django.core.cache import caches
from django.http import Http404, HttpResponse, HttpResponseNotFound
from django.shortcuts import render
from django.views.generic import TemplateView, View

from .boostrenderer import get_body_from_html, get_content_from_s3
from .markdown import process_md
from .tasks import adoc_to_html

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
        """Verifies the file and returns the raw static content from S3
        mangling paths using the stage_static_config.json settings
        """
        content_path = kwargs.get("content_path")

        # Try to get content from cache, if it's not there then fetch from S3
        content, content_type = self.get_content(content_path)

        if content is None:
            return HttpResponseNotFound("Page not found")  # Return a 404 response

        if content_type == "text/asciidoc":
            response = self.handle_adoc_content(request, content, content_type)
        else:
            response = HttpResponse(content, content_type=content_type)

        logger.info(
            "get_content_from_s3_view_success",
            key=kwargs.get("content_path"),
            status_code=response.status_code,
        )

        return response

    def get_content(self, content_path):
        """Get content from cache or S3."""
        static_content_cache = caches["static_content"]
        cache_key = f"static_content_{content_path}"
        cached_result = static_content_cache.get(cache_key)

        if cached_result:
            content, content_type = cached_result
        else:
            result = get_content_from_s3(key=content_path)
            if not result:
                logger.info(
                    "get_content_from_s3_view_no_valid_object",
                    key=content_path,
                    status_code=404,
                )
                return None, None  # Return None values when content is not found

            content, content_type = result

            # Always store the original content and content_type in cache
            static_content_cache.set(
                cache_key,
                (content, content_type),
                int(settings.CACHES["static_content"]["TIMEOUT"]),
            )

        return content, content_type

    def handle_adoc_content(self, request, content, content_path):
        """Convert AsciiDoc content to HTML and return the HTML response."""
        # Write the content to a temporary file
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(content)

        # Convert the AsciiDoc to HTML
        # TODO: Put this back on a delay and return a response indicating that
        # the content is being prepared
        html_content = adoc_to_html(
            temp_file.name, content_path, "text/asciidoc", delete_file=True
        )
        if isinstance(html_content, bytes):
            # Content is a byte string, decode it using UTF-8 encoding
            html_content = html_content.decode("utf-8")

        # Extract only the contents of the body tag from the HTML
        content = get_body_from_html(html_content)
        context = {"content": content, "content_type": "text/html"}
        return render(request, "adoc_content.html", context)
