import structlog

from celery.schedules import crontab

from config.celery import app
from libraries.github import LibraryUpdater


logger = structlog.getLogger(__name__)


@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    # Executes every 5th of the month at 7:30 a.m.
    sender.add_periodic_task(
        crontab(hour=7, minute=30, day_of_month=5),
        update_libraries.s(),
    )


@app.task
def update_libraries():
    """Update local libraries from GitHub Boost libraries.

    Use the LibraryUpdater, which retrieves the active boost libraries from the
    Boost GitHub repo, to update the models with the latest information on that
    library (repo) along with its issues, pull requests, and related objects
    from GitHub.

    """
    updater = LibraryUpdater()
    updater.update_libraries()

    logger.info("libraries_tasks_update_libraries_finished")
