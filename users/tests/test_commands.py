import pytest
from django.core.management import call_command
from model_bakery import baker

from users.models import UserProfileRoutingKey

pytestmark = pytest.mark.django_db


def rename_without_minting(user, display_name):
    """Rename `user` the way Django admin does: straight to the field.

    Neither profile form is involved, so no key is minted and the user is left
    with a URL built from their previous name -- the drift this command repairs.
    """
    user.display_name = display_name
    user.save(update_fields=["display_name"])
    return user


def test_mints_a_key_for_a_user_whose_name_changed_elsewhere():
    user = baker.make("users.User", display_name="Jane Doe", image=None)
    stale = user.profile_routing_keys.get().routing_key
    rename_without_minting(user, "Jane Smith")

    call_command("sync_profile_routing_keys")

    keys = list(user.profile_routing_keys.order_by("created"))
    assert keys[0].routing_key == stale
    assert keys[-1].routing_key.startswith("jane-smith-")
    assert user.profile_routing_keys.count() == 2


def test_leaves_a_user_whose_key_still_matches_alone():
    user = baker.make("users.User", display_name="Jane Doe", image=None)
    before = user.profile_routing_keys.get().routing_key

    call_command("sync_profile_routing_keys")

    assert user.profile_routing_keys.count() == 1
    assert user.profile_routing_keys.get().routing_key == before


def test_dry_run_reports_without_minting(capsys):
    user = baker.make("users.User", display_name="Jane Doe", image=None)
    rename_without_minting(user, "Jane Smith")

    call_command("sync_profile_routing_keys", "--dry-run")

    assert user.profile_routing_keys.count() == 1, "dry run must not write"
    output = capsys.readouterr().out
    assert "jane-smith" in output
    assert "would be minted" in output


def test_mints_for_a_user_with_no_key_at_all():
    """Fixture loads skip the creation hook, so a user can exist without one."""
    user = baker.make("users.User", display_name="Jane Doe", image=None)
    user.profile_routing_keys.all().delete()

    call_command("sync_profile_routing_keys")

    assert user.profile_routing_keys.get().routing_key.startswith("jane-doe-")


def test_skips_deactivated_users():
    """Their profile 404s, so a fresh URL would point at nothing."""
    user = baker.make("users.User", display_name="Jane Doe", image=None)
    rename_without_minting(user, "Jane Smith")
    user.is_active = False
    user.save(update_fields=["is_active"])

    call_command("sync_profile_routing_keys")

    assert user.profile_routing_keys.count() == 1


def test_is_safe_to_run_twice():
    user = baker.make("users.User", display_name="Jane Doe", image=None)
    rename_without_minting(user, "Jane Smith")

    call_command("sync_profile_routing_keys")
    call_command("sync_profile_routing_keys")

    assert user.profile_routing_keys.count() == 2, "the second run has nothing to do"


def test_reports_when_every_key_is_current(capsys):
    baker.make("users.User", display_name="Jane Doe", image=None)

    call_command("sync_profile_routing_keys")

    assert "every key is current" in capsys.readouterr().out


def test_does_not_move_a_url_for_a_cosmetic_rename():
    """Extra whitespace slugifies the same, so the URL should stay put."""
    user = baker.make("users.User", display_name="Jane Doe", image=None)
    before = user.profile_routing_keys.get().routing_key
    rename_without_minting(user, "  Jane   Doe  ")

    call_command("sync_profile_routing_keys")

    assert user.profile_routing_keys.count() == 1
    assert UserProfileRoutingKey.objects.get().routing_key == before
