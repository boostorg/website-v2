from django.apps import AppConfig
from django.core.signals import got_request_exception


class FeedbackConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "feedback"

    def ready(self):
        from feedback.diagnostics import record_server_error

        got_request_exception.connect(
            record_server_error, dispatch_uid="feedback_record_server_error"
        )
