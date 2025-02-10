import traceback
from contextlib import suppress

import djclick as click

from django.core.mail import send_mail
from django.utils import timezone
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.conf import settings
from slack_sdk.errors import SlackApiError

from core.githubhelper import GithubAPIClient
from libraries.forms import CreateReportForm
from libraries.tasks import update_commits
from slack.management.commands.fetch_slack_activity import get_my_channels, locked
from versions.models import Version

User = get_user_model()


def send_notification(user, message, subject="Task Started: release_tasks"):
    if user.email:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
        )


def progress_message(message: str):
    click.secho(message, fg="green")
    return f"{timezone.now()}: {message}"


@locked(1138692)
def run_commands(progress: list[str], generate_report: bool = False):
    if not settings.SLACK_BOT_TOKEN:
        raise ValueError("SLACK_BOT_TOKEN is not set.")
    handled_commits = {}
    progress.append(progress_message("Importing versions..."))
    call_command("import_versions", "--new")
    progress.append(progress_message("Finished importing versions."))
    latest_version: Version = Version.objects.most_recent()
    latest_version_name = latest_version.name

    progress.append(progress_message("Importing most recent beta version..."))
    call_command("import_beta_release", "--delete-versions")
    progress.append(progress_message("Finished importing most recent beta version."))

    progress.append(progress_message("Importing libraries..."))
    call_command("update_libraries")
    progress.append(progress_message("Finished importing libraries."))

    progress.append(progress_message("Saving library-version relationships..."))
    latest_version_number = latest_version_name.lstrip("boost-")
    call_command("import_library_versions", min_release=latest_version_number)
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
    handled_commits = update_commits(min_version=latest_version_name)
    progress.append(progress_message("Finished importing commits."))

    progress.append(progress_message("Syncing mailinglist statistics..."))
    call_command("sync_mailinglist_stats")
    progress.append(progress_message("Finished syncing mailinglist statistics."))

    progress.append(progress_message("Updating github issues..."))
    call_command("update_issues")
    progress.append(progress_message("Finished updating github issues..."))

    progress.append(progress_message("Updating slack activity buckets..."))
    call_command("fetch_slack_activity")
    progress.append(progress_message("Finished updating slack activity buckets."))

    if generate_report:
        progress.append(
            progress_message(f"Generating report for {latest_version_name}...")
        )
        form = CreateReportForm({"version": latest_version.id})
        form.cache_html()
        progress.append(
            progress_message(f"Finished generating report for {latest_version_name}.")
        )

    return handled_commits


def bad_credentials() -> list[str]:
    """This management command requires access to Slack and GitHub APIs.
    Checks that credentials are available and valid.

    Returns a list of credentials that are invalid or missing.

    Good return: []
    Bad return: ["GITHUB_TOKEN", "SLACK_BOT_TOKEN"]
    """
    possibly_bad_credentials = ["GITHUB_TOKEN", "SLACK_BOT_TOKEN"]
    if settings.GITHUB_TOKEN:
        client = GithubAPIClient(settings.GITHUB_TOKEN)
        if client.is_authenticated():
            # If this is true, the GitHub token is good
            possibly_bad_credentials.remove("GITHUB_TOKEN")

    if settings.SLACK_BOT_TOKEN:
        with suppress(SlackApiError):  # just breaks on this error
            next(get_my_channels())
            # If we get this far, the Slack token is good
            possibly_bad_credentials.remove("SLACK_BOT_TOKEN")

    return possibly_bad_credentials


@click.command()
@click.option(
    "--user_id",
    is_flag=False,
    help="The ID of the user that started this task (For notification purposes)",
    default=None,
)
@click.option(
    "--generate_report",
    is_flag=True,
    help="Generate a report at the end of the command",
    default=False,
)
def command(user_id=None, generate_report=False):
    """A long running chain of tasks to import and update library data."""
    start = timezone.now()

    user = None
    if user_id:
        user = User.objects.filter(id=user_id).first()

    progress = ["___Progress Messages___"]
    if missing_creds := bad_credentials():
        progress.append(
            progress_message(f"Missing credentials {', '.join(missing_creds)}")
        )
        if user:
            send_notification(
                user,
                message="Your task `release_tasks` failed.",
                subject="Task Failed: release_tasks",
            )
        return
    if user:
        send_notification(user, f"Your task `release_tasks` was started at: {start}")

    try:
        handled_commits = run_commands(progress, generate_report)
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
