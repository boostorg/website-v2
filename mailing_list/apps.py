from django.apps import AppConfig


class MailingListConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "mailing_list"

    def ready(self):
        from health_check.plugins import plugin_dir

        from mailing_list.health_checks import MailmanAPIHealthCheck

        plugin_dir.register(MailmanAPIHealthCheck)
