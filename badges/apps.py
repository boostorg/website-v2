"""App wiring for the achievements and badges system."""

from django.apps import AppConfig


class BadgesConfig(AppConfig):
    """App config for the achievements and badges system."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "badges"

    def ready(self):
        """Register the UserAchievement -> badge recalculation signals."""
        import badges.signals  # noqa
