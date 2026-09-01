from collections import namedtuple
from datetime import timedelta
from urllib.parse import quote

from allauth.socialaccount.models import SocialAccount
from django.conf import settings
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

from users.constants import (
    GITHUB_ACTIVITY_CARD_TITLE,
    GITHUB_ACTIVITY_POLL_INTERVAL_SECONDS,
    GITHUB_ACTIVITY_POLL_MAX_ATTEMPTS,
    GITHUB_ACTIVITY_REFRESH_LOCK_SECONDS,
    GITHUB_PROVIDER,
)

GithubActivityState = namedtuple(
    "GithubActivityState", ("linked", "activity", "refreshing")
)


def github_activity_state(user):
    """Return the GitHub activity card's state for a user.

    Reads the stored row only. A missing or stale row queues a background
    refresh, so a profile load never calls GitHub inline. ``activity`` is None
    when the user has no linked GitHub account or has never been synced.
    """
    linked = SocialAccount.objects.filter(user=user, provider=GITHUB_PROVIDER).exists()
    if not linked:
        return GithubActivityState(False, None, False)

    activity = getattr(user, "github_activity", None)
    if activity is not None and not activity.is_stale:
        return GithubActivityState(True, activity, False)

    _queue_github_activity_refresh(user)
    return GithubActivityState(True, activity, True)


def _queue_github_activity_refresh(user):
    """Queue a refresh unless one is already in flight for this user."""
    from users import tasks

    key = f"github_activity_refresh:{user.pk}"
    if cache.add(key, True, GITHUB_ACTIVITY_REFRESH_LOCK_SECONDS):
        tasks.refresh_github_activity.delay(user.pk)


def _plural(count, singular, plural):
    return f"{count} {singular if count == 1 else plural}"


def _repo_link(count, url):
    return f"[**{_plural(count, 'repository', 'repositories')}**]({url})"


def _search_url(login, terms, kind="pullrequests"):
    """Build a GitHub search URL scoped to the org and the card's time window.

    ``kind`` selects the search tab and must be passed explicitly: it cannot be
    inferred from ``terms``, since ``type:`` is not a commit-search qualifier.
    """
    since = (
        timezone.now() - timedelta(days=settings.BOOST_ACTIVITY_WINDOW_DAYS)
    ).date()
    query = quote(
        f"org:{settings.BOOST_GITHUB_ORG} {terms.format(login=login, since=since)}"
    )
    return f"https://github.com/search?q={query}&type={kind}"


def github_activity_bullets(data, login):
    """Render the stored activity numbers as the card's markdown bullet list.

    Lines with a zero count are omitted rather than rendered as "0 Commits".
    """
    bullets = []

    commits = data.get("total_commits") or 0
    if commits:
        url = _search_url(
            login, "author:{login} committer-date:>={since}", kind="commits"
        )
        bullets.append(
            f"* Created {_plural(commits, 'Commit', 'Commits')} in "
            f"{_repo_link(data.get('commit_repo_count') or 0, url)}"
        )

    repos_created = data.get("repos_created") or 0
    if repos_created:
        url = (
            f"https://github.com/orgs/{settings.BOOST_GITHUB_ORG}"
            "/repositories?sort=created"
        )
        bullets.append(f"* Created {_repo_link(repos_created, url)}")

    featured = data.get("featured_pr")
    if featured:
        comments = featured.get("comment_count") or 0
        bullets.append(
            f"* Created a pull request in "
            f"[**{featured['repo']}**]({featured['url']}) that received "
            f"{_plural(comments, 'comment', 'comments')}"
        )

    # The full total, not the total minus the featured PR. The line above
    # highlights one of these rather than excluding it, so every number on the
    # card matches what GitHub reports.
    prs_opened = data.get("prs_opened") or 0
    if prs_opened:
        url = _search_url(login, "author:{login} is:pr created:>={since}")
        bullets.append(
            f"* Opened {prs_opened} pull "
            f"{'request' if prs_opened == 1 else 'requests'} in "
            f"{_repo_link(data.get('pr_repo_count') or 0, url)}"
        )

    reviewed = data.get("prs_reviewed") or 0
    if reviewed:
        # Approximate: created:>= filters by when the PR was opened, while the
        # stored count is of review events. No query expresses the latter, so
        # this link can only ever be close.
        url = _search_url(login, "reviewed-by:{login} is:pr created:>={since}")
        bullets.append(
            f"* Reviewed {reviewed} pull "
            f"{'request' if reviewed == 1 else 'requests'} in "
            f"{_repo_link(data.get('review_repo_count') or 0, url)}"
        )

    return "\n".join(bullets)


def github_activity_card(user):
    """Build the context for the profile's GitHub activity card.

    Never calls GitHub. Returns one of three states: a connect prompt when no
    GitHub account is linked, an empty state while the first sync runs, or the
    stored numbers.
    """
    state = github_activity_state(user)
    card = {
        "title": GITHUB_ACTIVITY_CARD_TITLE,
        "linked": state.linked,
        "refreshing": state.refreshing,
        "markdown_text": "",
        "button_url": "",
        "button_label": "",
        "last_synced": None,
    }

    if not state.linked:
        card["markdown_text"] = (
            "Connect your GitHub account to see your Boost activity here."
        )
        card["button_label"] = "Connect GitHub"
        card["button_url"] = f"{reverse('github_login')}?process=connect"
        return card

    if state.activity is None or not state.activity.data:
        card["markdown_text"] = "Fetching your Boost GitHub activity…"
        return card

    # Every bullet is dropped when all counts are zero, which is the common case
    # for a linked account with no boostorg contributions yet.
    card["markdown_text"] = (
        github_activity_bullets(state.activity.data, user.github_username)
        or "No Boost contributions in the last 12 months"
    )
    card["last_synced"] = state.activity.last_synced
    card["button_url"] = user.github_profile_url or ""
    card["button_label"] = "View on GitHub"
    return card


def github_activity_card_context(user, attempt=0, include_hidden=False):
    """Context for ``_github_activity_card.html``, shared by the profile page
    and the fragment endpoint it polls.

    Returns None when the user has hidden their GitHub activity, unless
    ``include_hidden`` is set.
    Callers omit the section entirely rather than rendering it empty, the same
    shape ``badges.display.held_badges`` uses for ``hide_badges``.
    """
    if user.hide_github_activity and not include_hidden:
        return None

    attempt = max(0, attempt)
    # The poll address is per profile, so a visitor polling gets the numbers of
    # the profile they are on. An account with no routing key has no such
    # address. The card then renders once without polling rather than pointing
    # somewhere that 404s.
    key = user.profile_routing_key
    poll_url = reverse("profile-github-activity", args=[key.routing_key]) if key else ""
    return {
        "data": github_activity_card(user),
        "attempt": attempt,
        "next_attempt": attempt + 1,
        "poll_exhausted": attempt >= GITHUB_ACTIVITY_POLL_MAX_ATTEMPTS or not poll_url,
        "poll_url": poll_url,
        "poll_interval": GITHUB_ACTIVITY_POLL_INTERVAL_SECONDS,
    }
