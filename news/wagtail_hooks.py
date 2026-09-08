"""Wagtail admin hooks for the news app."""

from wagtail import hooks

from .constants import AI_DESCRIPTION_LIMIT_CHANGED_ACTION


@hooks.register("register_log_actions")
def register_ai_description_log_actions(actions):
    """Registers the AI description limit change action.

    Wagtail's own `wagtail.edit` entry records no field values, so the settings
    form logs this action instead to carry the old and new limit.
    """

    def message(data):
        change = data.get("daily_limit", {})
        return f"Daily limit changed from {change.get('old')} to {change.get('new')}"

    actions.register_action(
        AI_DESCRIPTION_LIMIT_CHANGED_ACTION, "AI description limit changed", message
    )
