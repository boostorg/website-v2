import os.path

from django.conf import settings
from django.http import Http404
from django.views.generic import TemplateView

from .markdown import process_md


class MarkdownTemplateView(TemplateView):
    template_name = "markdown_template.html"
    content_dir = settings.BOOST_CONTENT_DIR

    def build_path(self):
        """
        Builds the path from kwargs
        """
        directory = self.kwargs.get("directory1", None)
        directory2 = self.kwargs.get("directory2", None)
        filename = self.kwargs.get("title")

        if directory and directory2 and filename:
            return f"{self.content_dir}/{directory}/{directory2}/{filename}.html"
        elif directory and filename:
            return f"{self.content_dir}/{directory}/{filename}.html"
        elif filename:
            return f"{self.content_dir}/{filename}.html"
        else:
            return None

    def get(self, request, *args, **kwargs):
        """
        Verifies the file and returns the frontmatter and content
        """
        path = self.build_path()
        context = {}

        if not os.path.isfile(path):
            raise Http404("Post not found")

        context["frontmatter"], context["content"] = process_md(path)
        return self.render_to_response(context)
