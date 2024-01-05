import os

from celery import Celery
from celery.schedules import crontab


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


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")


# Schedule Celery tasks
@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    # Update library data from GitHub. Executes daily at 7:05 AM
    sender.add_periodic_task(
        crontab(hour=7, minute=5),
        "libraries.tasks.update_libraries",
    )

    # Clear the static content database cache. Executs daily at 4:05 AM.
    sender.add_periodic_task(
        crontab(hour=4, minute=5),
        "core.tasks.clear_static_content_cache",
    )
