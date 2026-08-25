from unittest.mock import patch
from django.core.cache import cache
from django.urls import reverse
from model_bakery import baker
from users.models import GithubActivity


def _connect(user):
    return baker.make(
        "socialaccount.SocialAccount",
        user=user,
        provider="github",
        extra_data={"login": "testuser"},
    )


def test_fragment_requires_login(client, db):
    resp = client.get(reverse("profile-github-activity"))
    assert resp.status_code == 302


def test_fragment_polls_while_refreshing(client, user, db):
    cache.clear()
    _connect(user)
    client.force_login(user)
    with patch("users.tasks.refresh_github_activity.delay"):
        resp = client.get(reverse("profile-github-activity"))
    html = resp.content.decode()
    assert resp.status_code == 200
    assert "hx-get=" in html
    assert 'hx-trigger="load delay:5s"' in html
    assert "Fetching GitHub activity" in html


def test_fragment_stops_polling_once_fresh(client, user, db):
    cache.clear()
    _connect(user)
    user.github_username = "testuser"
    user.save()
    GithubActivity.upsert_for_user(user, {"total_commits": 5, "commit_repo_count": 2})
    client.force_login(user)
    resp = client.get(reverse("profile-github-activity"))
    html = resp.content.decode()
    assert "hx-get=" not in html
    assert "Created 5 Commits" in html
    assert "Updated" in html


def test_fragment_gives_up_at_cap(client, user, db):
    cache.clear()
    _connect(user)
    client.force_login(user)
    with patch("users.tasks.refresh_github_activity.delay"):
        resp = client.get(reverse("profile-github-activity") + "?attempt=12")
    html = resp.content.decode()
    assert "hx-get=" not in html
    assert "reload the page" in html


def test_fragment_ignores_garbage_attempt(client, user, db):
    cache.clear()
    _connect(user)
    client.force_login(user)
    with patch("users.tasks.refresh_github_activity.delay"):
        resp = client.get(reverse("profile-github-activity") + "?attempt=abc")
    assert resp.status_code == 200
    assert "hx-get=" in resp.content.decode()
