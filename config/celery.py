import os
import datetime
from logging.config import dictConfig

from celery import Celery
from celery.schedules import crontab
from celery.signals import setup_logging
from pythonjsonlogger import jsonlogger

# set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("config")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django apps.
app.autodiscover_tasks()


@setup_logging.connect
def config_loggers(*args, **kwags):
    """Configure Celery logging with JSON default, readable for local development."""
    from django.conf import settings

    # production
    json_formatter = {
        "()": jsonlogger.JsonFormatter,
        "format": "%(name)s %(levelname)s %(filename)s:%(lineno)d %(message)s",
    }
    # local development
    text_formatter = {
        "format": "%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d - %(message)s",
        "datefmt": "%Y-%m-%d %H:%M:%S",
    }
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"json": json_formatter, "text": text_formatter},
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "text" if settings.LOCAL_DEVELOPMENT else "json",
                },
            },
            "root": {
                "level": "INFO",
                "handlers": ["console"],
            },
        }
    )


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")


@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Schedule Celery tasks via CeleryBeat."""

    # Update library data from GitHub. Executes daily at 7:05 AM
    sender.add_periodic_task(
        crontab(hour=7, minute=5),
        app.signature("libraries.tasks.update_libraries"),
    )

    # Update libraryversion dependencies. Executes daily at 8:05 AM
    sender.add_periodic_task(
        crontab(hour=8, minute=5),
        app.signature("libraries.tasks.update_library_version_dependencies"),
    )

    # Clear the static content database cache. Executes daily at 4:05 AM.
    sender.add_periodic_task(
        crontab(hour=4, minute=5),
        app.signature("core.tasks.clear_static_content_cache"),
    )

    # TODO: reenable
    # # Fetch Slack activity. Executes daily at 3:07 AM.
    # sender.add_periodic_task(
    #     crontab(hour=3, minute=7),
    #     app.signature("slack.tasks.fetch_slack_activity"),
    # )

    # delete users scheduled for deletion, arbitrarily every 61 minutes
    sender.add_periodic_task(
        datetime.timedelta(minutes=61),
        app.signature("users.tasks.do_scheduled_user_deletions"),
    )

    # Update data required for release report. Executes Saturday evenings.
    sender.add_periodic_task(
        crontab(day_of_week="sat", hour=20, minute=3),
        app.signature("libraries.tasks.release_tasks", generate_report=False),
    )

    # Update users' profile photos from GitHub. Executes daily at 3:30 AM.
    sender.add_periodic_task(
        crontab(hour=3, minute=30),
        app.signature("users.tasks.refresh_users_github_photos"),
    )

    # Clean up old sandbox documents. Executes weekly on Sundays at 2:00 AM.
    sender.add_periodic_task(
        crontab(day_of_week="sun", hour=2, minute=0),
        app.signature("asciidoctor_sandbox.tasks.cleanup_old_sandbox_documents"),
    )
