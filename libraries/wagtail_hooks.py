from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet

from .models import Category


class CategorySnippetViewSet(SnippetViewSet):
    model = Category
    menu_label = "Library Categories"
    icon = "tag"
    list_display = ["name", "short_description"]
    search_fields = ["name", "short_description"]
    panels = [
        "name",
        "slug",
        "short_description",
    ]


register_snippet(CategorySnippetViewSet)
