from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.utils import timezone
from model_bakery import baker

from users.constants import (
    GITHUB_ACTIVITY_POLL_MAX_ATTEMPTS,
    GITHUB_ACTIVITY_STALE_AFTER,
)
from users.models import GithubActivity
from users.profile_cards import (
    github_activity_bullets,
    github_activity_card_context,
    github_activity_card,
    github_activity_state,
)


def _connect_github(user):
    return baker.make(
        "socialaccount.SocialAccount",
        user=user,
        provider="github",
        extra_data={"login": "testuser"},
    )


def _store_activity(user, synced_ago):
    activity = GithubActivity.upsert_for_user(user, {"total_commits": 5})
    GithubActivity.objects.filter(pk=activity.pk).update(
        last_synced=timezone.now() - synced_ago
    )
    return GithubActivity.objects.get(pk=activity.pk)


def test_no_linked_account_returns_nothing_and_queues_nothing(user, db):
    cache.clear()

    with patch("users.tasks.refresh_github_activity.delay") as delay:
        linked, activity, refreshing = github_activity_state(user)

    assert linked is False
    assert activity is None
    assert refreshing is False
    delay.assert_not_called()


def test_fresh_activity_is_served_without_refreshing(user, db):
    cache.clear()
    _connect_github(user)
    _store_activity(user, timedelta(hours=1))
    user.refresh_from_db()

    with patch("users.tasks.refresh_github_activity.delay") as delay:
        linked, activity, refreshing = github_activity_state(user)

    assert linked is True
    assert activity is not None
    assert refreshing is False
    delay.assert_not_called()


def test_stale_activity_is_served_while_refresh_is_queued(user, db):
    """Stale data still renders; the refresh happens in the background."""
    cache.clear()
    _connect_github(user)
    _store_activity(user, GITHUB_ACTIVITY_STALE_AFTER + timedelta(minutes=1))
    user.refresh_from_db()

    with patch("users.tasks.refresh_github_activity.delay") as delay:
        linked, activity, refreshing = github_activity_state(user)

    assert linked is True
    assert activity is not None
    assert activity.data == {"total_commits": 5}
    assert refreshing is True
    delay.assert_called_once_with(user.pk)


def test_linked_but_never_synced_queues_refresh(user, db):
    cache.clear()
    _connect_github(user)

    with patch("users.tasks.refresh_github_activity.delay") as delay:
        linked, activity, refreshing = github_activity_state(user)

    assert linked is True
    assert activity is None
    assert refreshing is True
    delay.assert_called_once_with(user.pk)


def test_repeat_loads_do_not_queue_duplicate_refreshes(user, db):
    """A second page load while a refresh is in flight must not re-queue it."""
    cache.clear()
    _connect_github(user)

    with patch("users.tasks.refresh_github_activity.delay") as delay:
        github_activity_state(user)
        refreshing = github_activity_state(user).refreshing

    assert refreshing is True
    assert delay.call_count == 1


def test_is_stale_boundaries(user, db):
    activity = _store_activity(user, GITHUB_ACTIVITY_STALE_AFTER - timedelta(minutes=1))
    assert activity.is_stale is False

    activity = _store_activity(user, GITHUB_ACTIVITY_STALE_AFTER + timedelta(minutes=1))
    assert activity.is_stale is True

    activity.last_synced = None
    assert activity.is_stale is True


ACTIVITY_DATA = {
    "total_commits": 24,
    "commit_repo_count": 7,
    "repos_created": 1,
    "prs_opened": 18,
    "pr_repo_count": 6,
    "prs_reviewed": 3,
    "review_repo_count": 3,
    "featured_pr": {
        "title": "Add support",
        "url": "https://github.com/boostorg/url/pull/932",
        "repo": "boostorg/url",
        "comment_count": 6,
    },
}


def test_card_is_empty_without_a_linked_account(user, db):
    """Nothing to show and nothing to offer: connecting lives on the account
    connections card, so this card just reports that it has no data and its
    callers omit the section."""
    cache.clear()

    card = github_activity_card(user)

    assert card["linked"] is False
    assert card["markdown_text"] == ""
    assert card["button_label"] == ""
    assert card["button_url"] == ""


def test_card_shows_empty_state_when_linked_but_unsynced(user, db):
    cache.clear()
    _connect_github(user)

    with patch("users.tasks.refresh_github_activity.delay"):
        card = github_activity_card(user)

    assert "Fetching Boost GitHub activity" in card["markdown_text"]
    # Reads on anyone's profile, not just your own.
    assert "your" not in card["markdown_text"]
    assert card["refreshing"] is True
    assert card["button_url"] == ""


def test_card_renders_stored_numbers(user, db):
    cache.clear()
    _connect_github(user)
    user.github_username = "testuser"
    user.save()
    GithubActivity.upsert_for_user(user, ACTIVITY_DATA)
    user.refresh_from_db()

    card = github_activity_card(user)
    markdown = card["markdown_text"]

    assert "Created 24 Commits in [**7 repositories**]" in markdown
    assert "Created [**1 repository**]" in markdown
    assert "[**boostorg/url**](https://github.com/boostorg/url/pull/932)" in markdown
    assert "that received 6 comments" in markdown
    # The full total. The featured line above highlights one of these
    # rather than excluding it, so this matches what GitHub reports.
    assert "Opened 18 pull requests in [**6 repositories**]" in markdown
    assert "other pull request" not in markdown
    assert "Reviewed 3 pull requests in [**3 repositories**]" in markdown
    assert card["button_label"] == "View on GitHub"
    assert card["button_url"] == "https://github.com/testuser"
    assert card["refreshing"] is False


def test_bullets_omit_zero_counts():
    markdown = github_activity_bullets(
        {"total_commits": 0, "prs_reviewed": 2, "review_repo_count": 1}, "testuser"
    )

    assert "Commit" not in markdown
    assert "Reviewed 2 pull requests in [**1 repository**]" in markdown


def test_bullets_singularise():
    markdown = github_activity_bullets(
        {
            "total_commits": 1,
            "commit_repo_count": 1,
            "prs_reviewed": 1,
            "review_repo_count": 1,
        },
        "testuser",
    )

    assert "Created 1 Commit in [**1 repository**]" in markdown
    assert "Reviewed 1 pull request in [**1 repository**]" in markdown


def test_bullets_scope_search_links_to_boostorg():
    markdown = github_activity_bullets(
        {"total_commits": 3, "commit_repo_count": 2}, "testuser"
    )

    assert "org%3Aboostorg" in markdown
    assert "author%3Atestuser" in markdown


def test_poll_context_stops_at_attempt_cap(user, db):
    cache.clear()
    _connect_github(user)

    with patch("users.tasks.refresh_github_activity.delay"):
        ctx = github_activity_card_context(
            user, attempt=GITHUB_ACTIVITY_POLL_MAX_ATTEMPTS
        )

    assert ctx["poll_exhausted"] is True
    assert ctx["data"]["refreshing"] is True


def test_poll_context_continues_below_cap(user, db):
    cache.clear()
    _connect_github(user)

    with patch("users.tasks.refresh_github_activity.delay"):
        ctx = github_activity_card_context(user, attempt=1)

    assert ctx["poll_exhausted"] is False
    assert ctx["next_attempt"] == 2


def test_poll_context_clamps_negative_attempt(user, db):
    cache.clear()

    ctx = github_activity_card_context(user, attempt=-5)

    assert ctx["attempt"] == 0


def test_bullets_follow_the_configured_org(settings):
    """The search and repo links must come from BOOST_GITHUB_ORG, not a literal."""
    settings.BOOST_GITHUB_ORG = "someotherorg"

    markdown = github_activity_bullets(
        {"total_commits": 3, "commit_repo_count": 2, "repos_created": 1}, "testuser"
    )

    assert "org%3Asomeotherorg" in markdown
    assert "/orgs/someotherorg/repositories" in markdown
    assert "boostorg" not in markdown


ZERO_ACTIVITY_DATA = {
    "total_commits": 0,
    "commit_repo_count": 0,
    "repos_created": 0,
    "prs_opened": 0,
    "pr_repo_count": 0,
    "prs_reviewed": 0,
    "review_repo_count": 0,
    "featured_pr": None,
}


def test_card_shows_empty_state_when_there_are_no_contributions(user, db):
    """A linked account with no boostorg activity must not render a blank card."""
    cache.clear()
    _connect_github(user)
    user.github_username = "testuser"
    user.save()
    GithubActivity.upsert_for_user(user, ZERO_ACTIVITY_DATA)
    user.refresh_from_db()

    card = github_activity_card(user)

    assert card["markdown_text"] == "No Boost contributions in the last 12 months"
    # Still a real linked account, so the profile link stays useful.
    assert card["button_label"] == "View on GitHub"
    assert card["button_url"] == "https://github.com/testuser"
    assert card["refreshing"] is False
    assert card["last_synced"] is not None


def test_card_with_contributions_does_not_show_the_empty_state(user, db):
    cache.clear()
    _connect_github(user)
    user.github_username = "testuser"
    user.save()
    GithubActivity.upsert_for_user(user, {"total_commits": 3, "commit_repo_count": 1})
    user.refresh_from_db()

    card = github_activity_card(user)

    assert "No Boost contributions" not in card["markdown_text"]
    assert "Created 3 Commits" in card["markdown_text"]


def test_search_links_are_scoped_to_the_activity_window(settings):
    """Links must carry the same 12-month window the stored numbers cover."""
    settings.BOOST_ACTIVITY_WINDOW_DAYS = 365
    since = (timezone.now() - timedelta(days=365)).date()

    markdown = github_activity_bullets(
        {
            "total_commits": 3,
            "commit_repo_count": 1,
            "prs_opened": 2,
            "pr_repo_count": 1,
            "prs_reviewed": 4,
            "review_repo_count": 1,
        },
        "testuser",
    )

    assert f"committer-date%3A%3E%3D{since}" in markdown
    assert markdown.count(f"created%3A%3E%3D{since}") == 2  # PRs and reviews


def test_commits_link_targets_the_commits_tab():
    """type:commit is not a commit-search qualifier and returns nothing."""
    markdown = github_activity_bullets(
        {"total_commits": 3, "commit_repo_count": 1}, "testuser"
    )

    assert "type=commits" in markdown
    assert "type%3Acommit" not in markdown


def test_pr_and_review_links_target_the_pull_requests_tab():
    markdown = github_activity_bullets(
        {
            "prs_opened": 2,
            "pr_repo_count": 1,
            "prs_reviewed": 4,
            "review_repo_count": 1,
        },
        "testuser",
    )

    assert markdown.count("type=pullrequests") == 2
    assert "type=commits" not in markdown
