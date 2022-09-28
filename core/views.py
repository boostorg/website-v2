import os.path

from django.http import Http404
from django.views.generic import TemplateView

from .markdown import process_md


class MarkdownTemplateView(TemplateView):
    template_name = "markdown_template.html"

    def get(self, request, *args, **kwargs):
        filename = self.kwargs.get("title")
        if not os.path.isfile(f"content/{filename}.md"):
            raise Http404("Post not found")

        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filename = self.kwargs.get("title")
        metadata, content = process_md(f"content/{filename}.md")
        context["frontmatter"] = metadata
        context["content"] = content
        return context
