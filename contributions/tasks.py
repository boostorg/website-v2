from celery import shared_task
from structlog import get_logger

from contributions.constants import BULK_CREATE_BATCH_SIZE
from contributions.models import GitContribution, GithubContribution
from contributions.parsers.git_repositories import get_library_commit_contributions
from contributions.parsers.github_issues import get_library_issue_contributions
from contributions.parsers.github_pull_requests import get_library_pr_contributions
from core.githubhelper import GithubAPIClient
import libraries.constants as libraries_constants
from libraries.models import Library

logger = get_logger(__name__)


# Design note: the issues list endpoint contains pull requests too, but
#  the pull request/timeline api endpoints contain important information we
#  need that the issues list endpoint lacks.
def update_contribution_commits(
    library_key: str, library_id: int, github_repo: str, client: GithubAPIClient
) -> None:
    logger.info(f"Updating contributions - commits, {library_key=}")
    GitContribution.objects.bulk_create(
        get_library_commit_contributions(library_key, library_id, github_repo, client),
        ignore_conflicts=True,
        batch_size=BULK_CREATE_BATCH_SIZE,
    )


def update_contributions_prs(github_repo: str, client: GithubAPIClient) -> None:
    logger.info(f"Updating contributions - pull requests, {github_repo=}")
    GithubContribution.objects.bulk_create(
        get_library_pr_contributions(github_repo, client),
        ignore_conflicts=True,
        batch_size=BULK_CREATE_BATCH_SIZE,
    )


def update_contributions_issues(github_repo: str, client: GithubAPIClient) -> None:
    logger.info(f"Updating contributions - issues, {github_repo=}")
    GithubContribution.objects.bulk_create(
        get_library_issue_contributions(github_repo, client),
        ignore_conflicts=True,
        batch_size=BULK_CREATE_BATCH_SIZE,
    )


def update_library_contributions(
    library_key: str, library_id: int, client: GithubAPIClient
) -> None:
    library = Library.objects.filter(key=library_key).first()
    if not library:
        logger.warning(f"No library with key={library_key} found")
        return
    logger.info(f"Updating contributions data for {library=}/{library.github_repo=}")
    try:
        update_contribution_commits(
            library_key, library_id, library.github_repo, client
        )
        # the question of repo vs library key is up in the air at the moment, the original spec called for repo in
        # github contribution entries so here we continue with that
        update_contributions_prs(library.github_repo, client)
        update_contributions_issues(library.github_repo, client)
    except Exception:
        logger.exception(
            f"error updating contributions data for {library=}/{library_key=}"
        )


@shared_task
def update_contributions(github_token: str = None) -> None:
    client = GithubAPIClient(token=github_token)
    logger.info("Updating contributions for all libraries")

    libraries = Library.objects.all().order_by("name")
    for library in libraries:
        if library.key in libraries_constants.SKIP_MODULES:
            logger.info(f"Skipping {library.key=} (in SKIP_MODULES)")
            continue

        logger.info(f"Processing library: {library.key} ({library.name})")
        try:
            update_library_contributions(library.key, library.id, client)
        except Exception:
            logger.exception(f"Failed to update contributions for {library.key=}")
