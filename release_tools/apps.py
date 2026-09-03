"""App wiring for the release maintenance tools in the admin."""

from django.apps import AppConfig


class ReleaseToolsConfig(AppConfig):
    """Gives the release maintenance jobs their own admin section.

    An app of its own only so the admin index has somewhere to put them: the
    index groups by app, and these jobs are operator tooling rather than part of
    any one model's administration. No models of its own beyond the proxy the
    admin page hangs off.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "release_tools"
    verbose_name = "Release tools"
