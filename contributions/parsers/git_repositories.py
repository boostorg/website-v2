from typing import Iterable
from datetime import datetime
import structlog
from contributions.models import GitContribution, Email, GitProfile, Identity
from core.githubhelper import GithubAPIClient
from libraries.github import ParsedCommit

logger = structlog.get_logger(__name__)


def parsed_commit_to_git_contribution(
    commit: ParsedCommit, library_key: str, library_id: int
) -> GitContribution:
    email, _ = Email.objects.get_or_create(email=commit.email)

    # Use actual commit author name if available, fall back to email username
    profile_name = commit.name if commit.name else commit.email.split("@")[0]

    git_profile, created = GitProfile.objects.update_or_create(
        email=email, defaults={"name": profile_name}
    )

    if created:
        identity = Identity.objects.create(name=git_profile.name)
        git_profile.identity = identity
        git_profile.save()

    return GitContribution(
        profile=git_profile,
        contributed_at=commit.committed_at,
        repo=library_key,
        library_id=library_id,
        info=commit.sha,
        comment=commit.message,
    )


def get_new_library_commits(
    library_key: str, github_repo: str, client: GithubAPIClient, branch: str = "master"
) -> Iterable[ParsedCommit]:
    most_recent_commit = (
        GitContribution.objects.filter(repo=library_key)
        .order_by("-contributed_at")
        .first()
    )
    since = most_recent_commit.contributed_at if most_recent_commit else None
    logger.info(f"updating library commits for {library_key=} {github_repo=} {since=}")
    for commit in client.get_commits(github_repo, branch, since):
        yield ParsedCommit(
            email=commit["commit"]["author"]["email"],
            name=commit["commit"]["author"]["name"],
            message=commit["commit"]["message"],
            sha=commit["sha"],
            version="master",
            is_merge=len(commit["parents"]) > 1,
            committed_at=datetime.fromisoformat(commit["commit"]["author"]["date"]),
            avatar_url=commit["commit"]["author"].get("avatar_url", ""),
        )


def get_library_commit_contributions(
    library_key: str, library_id: int, github_repo: str, client: GithubAPIClient
) -> Iterable[GitContribution]:
    logger.info(f"getting commit data for {library_key=}")
    for item in get_new_library_commits(library_key, github_repo, client):
        yield parsed_commit_to_git_contribution(item, library_key, library_id)
