"""Wagtail admin panels for the news app."""

from wagtail.admin.panels import Panel
from wagtail.log_actions import registry as log_registry

from .constants import AI_DESCRIPTION_LIMIT_CHANGED_ACTION

# Change entries rendered under the limit. Enough to answer "who moved this and
# when" at a glance without turning the settings screen into a log viewer.
RECENT_CHANGES_DISPLAYED = 5


class AIDescriptionUsagePanel(Panel):
    """Read-only panel showing today's generation usage and recent limit changes.

    Wagtail's settings URLs register no history view, so without this the
    `wagtail.edit` log entries the edit view writes would be invisible in the
    CMS. Rendering usage and history next to the field also satisfies the
    ticket's "without leaving that screen" requirement.
    """

    def __init__(self, **kwargs):
        kwargs.setdefault("heading", "Usage and history")
        super().__init__(**kwargs)

    class BoundPanel(Panel.BoundPanel):
        """Renders the usage figures for the current UTC day."""

        template_name = "news/panels/ai_description_usage.html"

        def get_context_data(self, parent_context=None):
            """Adds today's counts and the recent change log to the template."""
            from .services import description_generation_usage_today

            context = super().get_context_data(parent_context)
            context["usage"] = description_generation_usage_today()
            context["recent_changes"] = self.recent_changes()
            return context

        def recent_changes(self):
            """Most recent edits to this setting, newest first."""
            if self.instance.pk is None:
                return []
            logs = log_registry.get_logs_for_instance(self.instance)
            return logs.filter(
                action=AI_DESCRIPTION_LIMIT_CHANGED_ACTION
            ).select_related("user")[:RECENT_CHANGES_DISPLAYED]
