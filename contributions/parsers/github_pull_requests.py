import structlog
from datetime import datetime
from typing import Iterable, Optional

from contributions.models import ContributionType, GithubContribution
from contributions.parsers.utils import (
    get_gh_contributions_from_parsed_contributions,
    merge_content_for_comment,
    get_ghost_msg,
)
from core.githubhelper import GithubAPIClient
from libraries.github import ParsedGithubContribution, ParsedGithubUser

logger = structlog.get_logger(__name__)


def get_latest_pr_contribution_timestamp(repo: str) -> Optional[datetime]:
    """
    Get the timestamp of the most recent PR contribution for a repo.

    @param repo: Repository key
    @return: Most recent PR contribution timestamp, or None if no contributions exist
    """
    return (
        GithubContribution.objects.filter(
            repo=repo,
            type__in=[
                ContributionType.PR_CREATE,
                ContributionType.PR_COMMENT,
                ContributionType.PR_REVIEW,
                ContributionType.PR_MERGE,
                ContributionType.PR_CLOSE,
            ],
        )
        .order_by("-contributed_at")
        .values_list("contributed_at", flat=True)
        .first()
    )


def get_library_pr_contributions(
    github_repo: str, client: GithubAPIClient
) -> Iterable[GithubContribution]:
    if since := get_latest_pr_contribution_timestamp(github_repo):
        logger.info(f"Fetching PRs for {github_repo} updated since {since}")
    else:
        logger.info(f"Fetching all PRs for {github_repo} - first sync")

    for pr in client.get_prs_graphql(github_repo, since=since):
        logger.info(f"Recording pull request: {github_repo=} {pr['number']=}")

        pr_opened = get_pr_opened(pr, github_repo)
        pr_timeline_contributions = get_pr_timeline_contributions(pr, github_repo)
        pr_review_thread_contributions = get_pr_review_thread_contributions(
            pr, github_repo
        )

        yield from get_gh_contributions_from_parsed_contributions(
            pr_opened, pr_timeline_contributions, pr_review_thread_contributions
        )


def get_pr_opened(pr: dict, github_repo: str) -> Iterable[ParsedGithubContribution]:
    if not (user := ParsedGithubUser.from_graphql(pr.get("author"))):
        return

    yield ParsedGithubContribution(
        user=user,
        repo=github_repo,
        type=ContributionType.PR_CREATE,
        info=str(pr["number"]),
        comment=merge_content_for_comment(pr),
        contributed_at=datetime.fromisoformat(pr["createdAt"]),
    )


def get_pr_timeline_contributions(
    pr: dict, github_repo: str
) -> Iterable[ParsedGithubContribution]:
    """Parse timeline events (comments, close, merge) from GraphQL response."""
    event_type_map = {
        "IssueComment": ContributionType.PR_COMMENT,
        "ClosedEvent": ContributionType.PR_CLOSE,
        "MergedEvent": ContributionType.PR_MERGE,
    }

    for event in pr.get("timelineItems", {}).get("nodes", []):
        user_data = event.get("author") or event.get("actor") or event.get("user")
        timestamp = event.get("createdAt") or event.get("submittedAt")
        typename = event.get("__typename")

        if not timestamp or typename not in event_type_map:
            continue
        if not (user := ParsedGithubUser.from_graphql(user_data)):
            logger.debug(get_ghost_msg(github_repo, pr["number"], event["id"]))
            continue

        yield ParsedGithubContribution(
            user=user,
            repo=github_repo,
            type=event_type_map[typename],
            info=str(pr["number"]),
            comment=event.get("body"),
            contributed_at=datetime.fromisoformat(timestamp),
        )


def get_pr_review_thread_contributions(
    pr: dict, github_repo: str
) -> Iterable[ParsedGithubContribution]:
    """Parse review thread comments from GraphQL response."""
    for thread in pr.get("reviewThreads", {}).get("nodes", []):
        for comment in thread.get("comments", {}).get("nodes", []):
            if not (user := ParsedGithubUser.from_graphql(comment.get("author"))):
                logger.debug(get_ghost_msg(github_repo, pr["number"], comment["id"]))
                continue

            yield ParsedGithubContribution(
                user=user,
                repo=github_repo,
                type=ContributionType.PR_REVIEW,
                info=str(pr["number"]),
                comment=comment.get("body"),
                contributed_at=datetime.fromisoformat(comment["createdAt"]),
            )
