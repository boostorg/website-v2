import structlog
from typing import Iterable, Optional
from datetime import datetime

from contributions.models import GithubContribution, ContributionType
from contributions.parsers.utils import (
    get_gh_contributions_from_parsed_contributions,
    merge_content_for_comment,
    get_ghost_msg,
)
from core.githubhelper import GithubAPIClient
from libraries.github import ParsedGithubContribution, ParsedGithubUser

logger = structlog.get_logger(__name__)


def get_latest_issue_contribution_timestamp(github_repo: str) -> Optional[datetime]:
    """
    Get the timestamp of the most recent issue contribution for a repo.

    @param repo: Repository key
    @return: Most recent issue contribution timestamp, or None if no contributions exist
    """
    return (
        GithubContribution.objects.filter(
            repo=github_repo,
            type__in=[
                ContributionType.ISSUE_CREATE,
                ContributionType.ISSUE_COMMENT,
                ContributionType.ISSUE_CLOSE,
                ContributionType.ISSUE_REOPENED,
            ],
        )
        .order_by("-contributed_at")
        .values_list("contributed_at", flat=True)
        .first()
    )


def get_library_issue_contributions(
    github_repo: str, client: GithubAPIClient
) -> Iterable[GithubContribution]:
    if since := get_latest_issue_contribution_timestamp(github_repo):
        logger.info(f"Fetching issues for {github_repo} updated since {since}")
    else:
        logger.info(f"Fetching all issues for {github_repo} (first sync)")

    for issue in client.get_issues_graphql(github_repo, since=since):
        logger.info(f"Recording {github_repo=} {issue['number']=}")
        issue_created = get_issue_created(issue, github_repo)
        issue_contributions = get_issue_contributions(issue, github_repo)

        yield from get_gh_contributions_from_parsed_contributions(
            issue_created,
            issue_contributions,
        )


def get_issue_created(
    issue: dict, github_repo: str
) -> Iterable[ParsedGithubContribution]:
    if not (user := ParsedGithubUser.from_graphql(issue.get("author"))):
        return

    yield ParsedGithubContribution(
        user=user,
        repo=github_repo,
        type=ContributionType.ISSUE_CREATE,
        info=str(issue["number"]),
        comment=merge_content_for_comment(issue),
        contributed_at=datetime.fromisoformat(issue["createdAt"]),
    )


def get_issue_contributions(
    issue: dict, github_repo: str
) -> Iterable[ParsedGithubContribution]:
    """
    Combines timeline events (close, reopen) with comments, matching them by
    user ID and timestamp to determine the correct contribution type.
    """

    event_type_map = {
        "ClosedEvent": ContributionType.ISSUE_CLOSE,
        "ReopenedEvent": ContributionType.ISSUE_REOPENED,
    }

    timeline_events = {}
    # Here we iterate over the timeline first to determine which events (e.g. closed,
    #  reopened) we'll need to backfill with comments. We use the user id and created
    #  datetime as the key to match the type and content
    for event in issue.get("timelineItems", {}).get("nodes", []):
        typename = event.get("__typename")
        if typename not in event_type_map:
            continue

        if not (user := ParsedGithubUser.from_graphql(event.get("actor"))):
            # Can be debugged by looking for the timeline item id at
            #  https://api.github.com/repos/boostorg/{library}/issues/{issue_number}/timeline # noqa: E501
            logger.debug(get_ghost_msg(github_repo, issue["number"], event["id"]))
            continue

        created_at = event["createdAt"]
        key = (user.user_id, created_at)
        timeline_events[key] = event_type_map[typename]

    # Process comments, matching them with timeline events
    for comment in issue.get("comments", {}).get("nodes", []):
        if not (user := ParsedGithubUser.from_graphql(comment.get("author"))):
            continue

        created_at = comment["createdAt"]
        key = (user.user_id, created_at)

        yield ParsedGithubContribution(
            user=user,
            repo=github_repo,
            type=timeline_events.get(key, ContributionType.ISSUE_COMMENT),
            info=str(issue["number"]),
            comment=comment.get("body"),
            contributed_at=datetime.fromisoformat(created_at),
        )
