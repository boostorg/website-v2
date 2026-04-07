import itertools
from typing import Iterable

from contributions.models import GithubProfile, GithubContribution, Identity
from libraries.github import ParsedGithubContribution


def get_gh_contributions_from_parsed_contributions(
    *args: Iterable[ParsedGithubContribution],
) -> Iterable[GithubContribution]:
    for contribution in itertools.chain(*args):
        profile, created = GithubProfile.objects.update_or_create(
            github_user_id=contribution.user.user_id,
            defaults={
                "name": contribution.user.username,
            },
        )

        if created:
            identity = Identity.objects.create(name=profile.name)
            profile.identity = identity
            profile.save()

        result = GithubContribution(
            profile=profile,
            type=contribution.type,
            repo=contribution.repo,
            contributed_at=contribution.contributed_at,
            info=contribution.info,
            comment=contribution.comment,
        )
        yield result


def merge_content_for_comment(source_data: dict) -> str:
    content = []
    if source_data.get("title"):
        content.append(source_data["title"])
    if source_data.get("body"):
        content.append(source_data["body"])
    return "\n".join(content)


def get_ghost_msg(github_repo: str, issue_num: int, node_id: str) -> str:
    return (
        f"no actor, may be ghost user. Skipped timeline item with nodeId={node_id} on\n"
        f"https://api.github.com/repos/boostorg/{github_repo}/issues/{issue_num}/timeline \n"
        f"https://github.com/boostorg/{github_repo}/issues/{issue_num}/timeline"
    )
