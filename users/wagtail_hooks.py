# wagtail_hooks.py
from wagtail.admin.panels import FieldPanel
from wagtail.admin.ui.tables import UpdatedAtColumn
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet

from users.models import UserBiography


class UserBiographyViewSet(SnippetViewSet):
    model = UserBiography
    icon = "user"
    list_display = ["user", UpdatedAtColumn()]
    list_per_page = 50
    copy_view_enabled = False
    inspect_view_enabled = True

    panels = [FieldPanel("user", read_only=True), FieldPanel("value")]

    search_fields = ["user__first_name", "user__last_name", "user__email"]


register_snippet(UserBiographyViewSet)
