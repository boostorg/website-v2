import traceback

import djclick as click

from django.core.mail import send_mail
from django.utils import timezone
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.conf import settings

from libraries.tasks import update_commits
from slack.management.commands.fetch_slack_activity import locked


User = get_user_model()


def send_notification(user, message):
    if user.email:
        send_mail(
            "Task Started: release_tasks",
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
        )


def progress_message(message: str):
    click.secho(message, fg="green")
    return f"{timezone.now()}: {message}"


@locked(1138692)
def run_commands(progress: list[str]):
    if not settings.SLACK_BOT_TOKEN:
        raise ValueError("SLACK_BOT_TOKEN is not set.")
    handled_commits = {}
    progress.append(progress_message("Importing versions..."))
    call_command("import_versions", "--new")
    progress.append(progress_message("Finished importing versions."))

    progress.append(progress_message("Importing most recent beta version..."))
    call_command("import_beta_release", "--delete-versions")
    progress.append(progress_message("Finished importing most recent beta version."))

    progress.append(progress_message("Importing libraries"))
    call_command("update_libraries")
    progress.append(progress_message("Finished importing libraries."))

    progress.append(progress_message("Saving library-version relationships..."))
    call_command("import_library_versions")
    progress.append(progress_message("Finished saving library-version relationships."))

    progress.append(progress_message("Adding library maintainers..."))
    call_command("update_maintainers")
    progress.append(progress_message("Finished adding library maintainers."))

    progress.append(progress_message("Adding library authors..."))
    call_command("update_authors")
    progress.append(progress_message("Finished adding library authors."))

    progress.append(progress_message("Adding library version authors..."))
    call_command("update_library_version_authors")
    progress.append(progress_message("Finished adding library version authors."))

    progress.append(progress_message("Importing git commits..."))
    handled_commits = update_commits()
    progress.append(progress_message("Finished importing commits..."))

    progress.append(progress_message("Syncing mailinglist statistics..."))
    call_command("sync_mailinglist_stats")
    progress.append(progress_message("Finished syncing mailinglist statistics..."))

    progress.append(progress_message("Updating github issues..."))
    call_command("update_issues")
    progress.append(progress_message("Finished updating github issues..."))

    progress.append(progress_message("Updating slack activity buckets..."))
    call_command("fetch_slack_activity")
    progress.append(progress_message("Finished updating slack activity buckets..."))

    return handled_commits


@click.command()
@click.option(
    "--user_id",
    is_flag=False,
    help="The ID of the user that started this task (For notification purposes)",
    default=None,
)
def command(user_id=None):
    """A long running chain of tasks to import and update library data."""
    start = timezone.now()

    user = None
    if user_id:
        user = User.objects.filter(id=user_id).first()

    if user:
        send_notification(user, f"Your task `release_tasks` was started at: {start}")
    progress = ["___Progress Messages___"]
    handled_commits = {}
    try:
        handled_commits = run_commands(progress)
        end = timezone.now()
        progress.append(progress_message(f"All done! Completed in {end - start}"))
    except Exception:
        error = traceback.format_exc()
        message = [
            f"ERROR: There was an error while running release_tasks.\n\n{error}",
            "\n".join(progress),
        ]
        if user:
            send_notification(
                user,
                "\n\n".join(message),
            )
        raise
    else:
        zero_commit_libraries = [
            (key, val) for key, val in handled_commits.items() if val == 0
        ]
        message = [
            f"The task `release_tasks` was completed. Task took: {end - start}",
            "\n".join(progress),
        ]
        if zero_commit_libraries:
            zero_commit_message = [
                "The import_commits task did not find commits for these libraries.",
                "The task may need to re-run.",
            ]
            for lib, _ in zero_commit_libraries:
                zero_commit_message.append(lib)
            message.append("\n".join(zero_commit_message))
        if user:
            send_notification(
                user,
                "\n\n".join(message),
            )
