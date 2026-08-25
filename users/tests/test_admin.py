from unittest.mock import patch

import pytest
from django.contrib.auth.models import Permission
from django.test import Client
from django.urls import reverse


def _refresh_url(user):
    return reverse("admin:user_refresh_github_activity", args=[user.pk])


@pytest.fixture
def linked_user(user):
    user.github_username = "testuser"
    user.save()
    return user


def test_refresh_github_activity_rejects_get(client, super_user, linked_user, db):
    """Queueing work by GET would fire on prefetch and carries no CSRF token."""
    client.force_login(super_user)

    with patch("users.tasks.refresh_github_activity.delay") as delay:
        resp = client.get(_refresh_url(linked_user))

    assert resp.status_code == 405
    delay.assert_not_called()


def test_refresh_github_activity_requires_csrf_token(super_user, linked_user, db):
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(super_user)

    with patch("users.tasks.refresh_github_activity.delay") as delay:
        resp = csrf_client.post(_refresh_url(linked_user))

    assert resp.status_code == 403
    delay.assert_not_called()


def test_refresh_github_activity_denied_without_change_permission(
    client, staff_user, linked_user, db
):
    """Staff status alone must not allow queueing a refresh for another user."""
    client.force_login(staff_user)

    with patch("users.tasks.refresh_github_activity.delay") as delay:
        resp = client.post(_refresh_url(linked_user))

    assert resp.status_code == 403
    delay.assert_not_called()


def test_refresh_github_activity_allowed_with_change_permission(
    client, staff_user, linked_user, db
):
    staff_user.user_permissions.add(Permission.objects.get(codename="change_user"))
    client.force_login(staff_user)

    with patch("users.tasks.refresh_github_activity.delay") as delay:
        resp = client.post(_refresh_url(linked_user))

    assert resp.status_code == 302
    delay.assert_called_once_with(linked_user.pk)


def test_refresh_github_activity_allowed_for_superuser(
    client, super_user, linked_user, db
):
    client.force_login(super_user)

    with patch("users.tasks.refresh_github_activity.delay") as delay:
        resp = client.post(_refresh_url(linked_user))

    assert resp.status_code == 302
    delay.assert_called_once_with(linked_user.pk)


def test_refresh_github_activity_skips_user_without_handle(
    client, super_user, user, db
):
    client.force_login(super_user)

    with patch("users.tasks.refresh_github_activity.delay") as delay:
        resp = client.post(_refresh_url(user))

    assert resp.status_code == 302
    delay.assert_not_called()


def test_refresh_button_posts_with_csrf_token(client, super_user, linked_user, db):
    """The admin page must render the control as a CSRF-protected POST form."""
    client.force_login(super_user)

    html = client.get(
        reverse("admin:users_user_change", args=[linked_user.pk])
    ).content.decode()

    assert f'action="{_refresh_url(linked_user)}"' in html
    assert "csrfmiddlewaretoken" in html
    assert f'href="{_refresh_url(linked_user)}"' not in html
