import traceback

import djclick as click
from django.contrib.auth import get_user_model
from django.utils import timezone

from core.management.actions import (
    Action,
    ActionsManager,
    send_notification,
)

User = get_user_model()


class ImportNewVersionsManager(ActionsManager):
    def set_tasks(self):
        self.tasks = [
            Action("Importing Versions", ["import_versions", "--new=true"]),
            Action(
                "Importing Most Recent Beta",
                ["import_beta_release", "--delete-versions"],
            ),
            Action("Importing development versions", ["import_development_versions"]),
        ]


@click.command()
@click.option(
    "--user_id",
    is_flag=False,
    help="The ID of the user that started this task (For notification purposes)",
    default=None,
)
def command(user_id=None):
    """Import new versions, beta releases, and development versions."""
    start = timezone.now()
    user = User.objects.filter(id=user_id).first() if user_id else None
    progress = ["___Progress Messages___"]

    send_notification(
        user,
        f"Your task `import_new_versions` was started at: {start}",
        subject="Task Started: import_new_versions",
    )

    try:
        manager = ImportNewVersionsManager()
        manager.run_tasks()
        progress.extend(manager.progress_messages)
        end = timezone.now()
    except Exception:
        error = traceback.format_exc()
        message = [
            f"ERROR: There was an error while running import_new_versions.\n\n{error}",
            "\n".join(progress),
        ]
        send_notification(
            user, "\n\n".join(message), subject="Task Failed: import_new_versions"
        )
        raise

    message = [
        f"The task `import_new_versions` was completed. Task took: {end - start}",
        "\n".join(progress),
    ]
    send_notification(
        user,
        "\n\n".join(message),
        subject="Task Complete: import_new_versions",
    )
