from django_lookbook.preview import LookbookPreview
from django.template import Context, Template
from django.template.loader import render_to_string


class PartialTemplatesPreview(LookbookPreview):

    def header(self, **kwargs):
        """
        `includes/header.html` is a partial template, we can write preview for it in this way.

        **Markdown syntax is supported in docstring**
        """
        return render_to_string("includes/header.html")

    def footer(self, **kwargs):
        """
        We can write template code directly
        """
        template = Template(
            """<footer>Hello World</footer>""",
        )
        return template.render(Context({}))
