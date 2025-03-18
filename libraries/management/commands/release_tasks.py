import traceback
from contextlib import suppress
from dataclasses import dataclass
from typing import Callable

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
from reports.models import WebsiteStatReport
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


@dataclass
class ReleaseTask:
    """
    A distinct task to be completed.

    Action can be a callable or a list of string arguments to pass to `call_command`
    """

    description: str
    action: Callable | list[str]

    def run(self):
        if isinstance(self.action, Callable):
            self.action()
        else:
            call_command(*self.action)


class ReleaseTasksManager:
    latest_version: Version | None = None
    progress_messages: list[str] = []
    handled_commits: dict[str, int] = {}

    def __init__(self, should_generate_report: bool = False):
        self.should_generate_report = should_generate_report
        self.tasks = [
            ReleaseTask("Importing versions", self.import_versions),
            ReleaseTask(
                "Importing most recent beta version",
                ["import_beta_release", "--delete-versions"],
            ),
            ReleaseTask("Importing libraries", ["update_libraries"]),
            ReleaseTask(
                "Saving library-version relationships", self.import_library_versions
            ),
            ReleaseTask("Adding library maintainers", ["update_maintainers"]),
            ReleaseTask("Adding library authors", ["update_authors"]),
            ReleaseTask(
                "Adding library version authors", ["update_library_version_authors"]
            ),
            ReleaseTask("Importing git commits", self.handle_commits),
            ReleaseTask("Syncing mailinglist statistics", ["sync_mailinglist_stats"]),
            ReleaseTask("Updating github issues", ["update_issues"]),
            ReleaseTask("Updating slack activity buckets", ["fetch_slack_activity"]),
            ReleaseTask("Updating website statistics", self.update_website_statistics),
            ReleaseTask("Generating report", self.generate_report),
        ]

    def update_release_data(self) -> dict[str:int]:
        for task in self.tasks:
            self.progress_messages.append(progress_message(f"{task.description}..."))
            task.run()
            self.progress_messages.append(
                progress_message(f"Finished {task.description.lower()}")
            )
        return self.handled_commits

    def import_versions(self):
        call_command("import_versions", "--new")
        self.latest_version = Version.objects.most_recent()

    def import_library_versions(self):
        latest_version_number = self.latest_version.name.lstrip("boost-")
        call_command("import_library_versions", min_release=latest_version_number)

    def handle_commits(self):
        self.handled_commits = update_commits(min_version=self.latest_version.name)

    def update_website_statistics(self):
        report, _ = WebsiteStatReport.objects.get_or_create(version=self.latest_version)
        report.populate_from_api()

    def generate_report(self):
        if not self.should_generate_report:
            self.progress_messages.append(
                progress_message("Skipped - report generation not requested")
            )
            return
        form = CreateReportForm({"version": self.latest_version.id})
        form.cache_html()


@locked(1138692)
def run_commands(progress: list[str], generate_report: bool = False):
    manager = ReleaseTasksManager(should_generate_report=generate_report)
    handled_commits = manager.update_release_data()

    progress.extend(manager.progress_messages)

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
            subject="Task Complete: release_tasks",
        )
