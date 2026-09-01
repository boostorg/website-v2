from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.urls import reverse
from model_bakery import baker

from users.models import GithubActivity


def _connect(user, login="testuser"):
    return baker.make(
        "socialaccount.SocialAccount",
        user=user,
        provider="github",
        extra_data={"login": login},
    )


def _fragment_url(user, attempt=None):
    url = reverse(
        "profile-github-activity", args=[user.profile_routing_key.routing_key]
    )
    return f"{url}?attempt={attempt}" if attempt is not None else url


@pytest.fixture
def other_user(db):
    """A second user, to be looked at rather than logged in as."""
    return baker.make(
        "users.User",
        email="other@example.com",
        display_name="Other User",
        image=None,
    )


def test_fragment_is_public(client, user, db):
    """The profile page is public, so its polling endpoint must be too, or a
    signed-out visitor's card never updates."""
    cache.clear()
    _connect(user)

    with patch("users.tasks.refresh_github_activity.delay"):
        resp = client.get(_fragment_url(user))

    assert resp.status_code == 200


def test_fragment_serves_the_profile_in_the_url_not_the_viewer(
    client, user, other_user, db
):
    """The bug this endpoint shape prevents: signed in as one user, polling
    another's card must not swap in the viewer's own numbers."""
    cache.clear()
    _connect(user, login="viewer")
    user.github_username = "viewer"
    user.save()
    GithubActivity.upsert_for_user(user, {"total_commits": 111, "commit_repo_count": 1})

    _connect(other_user, login="subject")
    other_user.github_username = "subject"
    other_user.save()
    GithubActivity.upsert_for_user(
        other_user, {"total_commits": 222, "commit_repo_count": 1}
    )

    client.force_login(user)
    html = client.get(_fragment_url(other_user)).content.decode()

    assert "Created 222 Commits" in html
    assert "111" not in html


def test_fragment_404s_for_a_deactivated_account(client, other_user, db):
    """Matches the profile page, so the fragment cannot serve what the page
    itself refuses to."""
    cache.clear()
    _connect(other_user)
    url = _fragment_url(other_user)
    other_user.is_active = False
    other_user.save()

    assert client.get(url).status_code == 404


def test_fragment_404s_for_an_unknown_routing_key(client, db):
    assert client.get("/users/no-such-person/github-activity/").status_code == 404


def test_fragment_polls_while_refreshing(client, user, db):
    cache.clear()
    _connect(user)

    with patch("users.tasks.refresh_github_activity.delay"):
        resp = client.get(_fragment_url(user))

    html = resp.content.decode()
    assert resp.status_code == 200
    assert "hx-get=" in html
    assert 'hx-trigger="load delay:5s"' in html
    assert "Fetching GitHub activity" in html


def test_fragment_polls_its_own_profile_address(client, user, db):
    """Each response points the next poll at the same profile, so the chain
    cannot drift onto the viewer."""
    cache.clear()
    _connect(user)

    with patch("users.tasks.refresh_github_activity.delay"):
        html = client.get(_fragment_url(user)).content.decode()

    assert f'hx-get="{_fragment_url(user)}?attempt=1"' in html


def test_fragment_stops_polling_once_fresh(client, user, db):
    cache.clear()
    _connect(user)
    user.github_username = "testuser"
    user.save()
    GithubActivity.upsert_for_user(user, {"total_commits": 5, "commit_repo_count": 2})

    html = client.get(_fragment_url(user)).content.decode()

    assert "hx-get=" not in html
    assert "Created 5 Commits" in html
    assert "Updated" in html


def test_fragment_gives_up_at_cap(client, user, db):
    cache.clear()
    _connect(user)

    with patch("users.tasks.refresh_github_activity.delay"):
        html = client.get(_fragment_url(user, attempt=12)).content.decode()

    assert "hx-get=" not in html
    assert "reload the page" in html


def test_fragment_ignores_garbage_attempt(client, user, db):
    cache.clear()
    _connect(user)

    with patch("users.tasks.refresh_github_activity.delay"):
        resp = client.get(_fragment_url(user, attempt="abc"))

    assert resp.status_code == 200
    assert "hx-get=" in resp.content.decode()


def test_fragment_404s_when_activity_is_hidden(client, user, other_user, db):
    """Otherwise the endpoint is a way around the profile page's own rules."""
    cache.clear()
    _connect(other_user)
    other_user.hide_github_activity = True
    other_user.save()

    client.force_login(user)
    assert client.get(_fragment_url(other_user)).status_code == 404


def test_fragment_serves_hidden_activity_to_its_owner(client, user, db):
    cache.clear()
    _connect(user)
    user.github_username = "testuser"
    user.hide_github_activity = True
    user.save()
    GithubActivity.upsert_for_user(user, {"total_commits": 5, "commit_repo_count": 1})

    client.force_login(user)
    resp = client.get(_fragment_url(user))

    assert resp.status_code == 200
    assert "Created 5 Commits" in resp.content.decode()
