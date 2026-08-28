from unittest.mock import patch

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import Permission
from django.test import Client, RequestFactory
from django.urls import reverse
from model_bakery import baker

from users.admin import EmailUserAdmin
from users.models import User, UserProfileRoutingKey


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
    # The button sits in the submit row and reaches the form by id, so the
    # form itself can stay outside the admin form.
    assert 'form="refresh-github-activity"' in html


def test_refresh_form_is_not_nested_inside_the_admin_form(
    client, super_user, linked_user, db
):
    """HTML forbids nested forms: the browser drops the inner one, so the
    button would submit the change form, saving unsaved edits and queueing
    nothing. Our form must therefore sit before the admin form opens."""
    client.force_login(super_user)

    html = client.get(
        reverse("admin:users_user_change", args=[linked_user.pk])
    ).content.decode()

    refresh_form = html.index(f'action="{_refresh_url(linked_user)}"')
    admin_form = html.index('id="user_form"')

    assert refresh_form < admin_form


pytestmark = pytest.mark.django_db


def save_in_admin(user):
    """Save `user` the way the admin change form does."""
    model_admin = EmailUserAdmin(User, AdminSite())
    request = RequestFactory().post(f"/admin/users/user/{user.pk}/change/")
    model_admin.save_model(request, user, form=None, change=True)


def test_admin_rename_mints_a_new_key():
    """Editing display_name here bypasses both profile forms, so without this
    the user's URL would keep their old name."""
    user = baker.make("users.User", display_name="Jane Doe", image=None)
    before = user.profile_routing_keys.get().routing_key

    user.display_name = "Jane Smith"
    save_in_admin(user)

    keys = list(user.profile_routing_keys.order_by("created"))
    assert len(keys) == 2
    assert keys[0].routing_key == before
    assert keys[1].routing_key.startswith("jane-smith-")
    assert user.get_absolute_url() == f"/users/{keys[1].routing_key}/"


def test_admin_save_without_a_rename_keeps_the_url():
    """Saving an unrelated field must not move anyone's public URL."""
    user = baker.make("users.User", display_name="Jane Doe", image=None)
    before = user.profile_routing_keys.get().routing_key

    user.valid_email = False
    save_in_admin(user)

    assert user.profile_routing_keys.count() == 1
    assert user.profile_routing_keys.get().routing_key == before


def test_admin_save_does_not_mint_for_a_deactivated_account():
    """Account deletion drops the keys on purpose; minting one back from an
    admin save would undo that."""
    user = baker.make("users.User", display_name="Jane Doe", image=None)
    user.profile_routing_keys.all().delete()
    user.is_active = False

    save_in_admin(user)

    assert not user.profile_routing_keys.exists()


def test_admin_save_mints_for_a_user_with_no_key():
    """A user created outside the ORM hook (loaddata) gets one on the next
    admin save."""
    user = baker.make("users.User", display_name="Jane Doe", image=None)
    UserProfileRoutingKey.objects.filter(user=user).delete()

    save_in_admin(user)

    assert user.profile_routing_keys.get().routing_key.startswith("jane-doe-")
