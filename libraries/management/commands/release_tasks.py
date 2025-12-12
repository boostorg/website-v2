import traceback
from contextlib import suppress
from datetime import timedelta

import djclick as click

from django.utils import timezone
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.conf import settings
from slack_sdk.errors import SlackApiError

from core.githubhelper import GithubAPIClient
from core.management.actions import (
    progress_message,
    Action,
    ActionsManager,
    send_notification,
)
from libraries.tasks import update_commits, generate_release_report
from reports.models import WebsiteStatReport
from slack.management.commands.fetch_slack_activity import get_my_channels, locked
from versions.models import Version, ReportConfiguration

User = get_user_model()


class ReleaseTasksManager(ActionsManager):
    latest_version: Version | None = None
    handled_commits: dict[str, int] = {}

    def __init__(
        self, base_uri: str, user_id: int, should_generate_report: bool = False
    ):
        self.base_uri = base_uri
        self.should_generate_report = should_generate_report
        self.user_id = user_id
        super().__init__()

    def set_tasks(self):
        self.tasks = [
            Action("Importing versions", self.import_versions),
            Action(
                "Importing most recent beta version",
                ["import_beta_release", "--delete-versions"],
            ),
            Action("Importing libraries", ["update_libraries"]),
            Action(
                "Saving library-version relationships", self.import_library_versions
            ),
            Action("Adding library maintainers", ["update_maintainers"]),
            Action("Adding library authors", ["update_authors"]),
            Action(
                "Adding library version authors", ["update_library_version_authors"]
            ),
            Action("Importing git commits", self.import_commits),
            Action("Syncing mailinglist statistics", ["sync_mailinglist_stats"]),
            Action("Updating github issues", ["update_issues"]),
            Action("Updating slack activity buckets", ["fetch_slack_activity"]),
            Action("Updating website statistics", self.update_website_statistics),
            Action("Importing mailing list counts", self.import_ml_counts),
            # Action("Generating report", self.generate_report),
        ]

    def import_versions(self):
        call_command("import_versions")
        self.latest_version = Version.objects.most_recent()

    def import_library_versions(self):
        latest_version_number = self.latest_version.name.lstrip("boost-")
        call_command("import_library_versions", min_release=latest_version_number)

    def import_commits(self):
        self.handled_commits = update_commits(min_version=self.latest_version.name)

    def update_website_statistics(self):
        report, _ = WebsiteStatReport.objects.get_or_create(version=self.latest_version)
        report.populate_from_api()

    def import_ml_counts(self):
        """Import counts for the last four months. Should be more than enough,
        and saves lots of time vs importing all.
        """
        start_date = timezone.now() - timedelta(days=120)
        date_string = start_date.strftime("%Y-%m-%d")
        call_command("import_ml_counts", start_date=date_string)

    def generate_report(self):
        if not self.should_generate_report:
            self.add_progress_message("Skipped - report generation not requested")
            return

        report_configuration = ReportConfiguration.objects.get(
            version=self.latest_version.name
        )
        generate_release_report.delay(
            user_id=self.user_id,
            params={"report_configuration": report_configuration.id, "publish": True},
            base_uri=self.base_uri,
        )


@locked(1138692)
def run_commands(
    progress: list[str], base_uri: str, user_id: int, generate_report: bool = False
):
    manager = ReleaseTasksManager(
        base_uri=base_uri,
        should_generate_report=generate_report,
        user_id=user_id,
    )
    manager.run_tasks()
    progress.extend(manager.progress_messages)
    return manager.handled_commits


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
    "--base_uri",
    is_flag=False,
    help="The URI to which paths should be relative",
    default=None,
)
@click.option(
    "--user_id",
    is_flag=False,
    help="The ID of the user that started this task (For notification purposes)",
)
@click.option(
    "--generate_report",
    is_flag=True,
    help="Generate a report at the end of the command",
    default=False,
)
def command(user_id, base_uri=None, generate_report=False):
    """A long running chain of tasks to import and update library data."""
    start = timezone.now()

    user = User.objects.filter(id=user_id).first()

    progress = ["___Progress Messages___"]
    if missing_creds := bad_credentials():
        progress.append(
            progress_message(f"Missing credentials {', '.join(missing_creds)}")
        )
        send_notification(
            user,
            message="Your task `release_tasks` failed.",
            subject="Task Failed: release_tasks",
        )
        return

    send_notification(
        user,
        f"Your task `release_tasks` was started at: {start}",
        subject="Task Started: release_tasks",
    )

    try:
        handled_commits = run_commands(progress, base_uri, generate_report, user_id)
        end = timezone.now()
    except Exception:
        error = traceback.format_exc()
        message = [
            f"ERROR: There was an error while running release_tasks.\n\n{error}",
            "\n".join(progress),
        ]
        send_notification(
            user, "\n\n".join(message), subject="Task Failed: release_tasks"
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
    send_notification(
        user,
        "\n\n".join(message),
        subject="Task Complete: release_tasks",
    )
