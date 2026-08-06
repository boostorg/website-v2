import pytest
from django.db.models.signals import post_save
from model_bakery import baker

from users.models import User, UserProfileRoutingKey
from users.utils import (
    ROUTING_KEY_FALLBACK_BASE,
    ROUTING_KEY_SUFFIX_LENGTH,
    generate_routing_key,
    routing_key_base,
)

pytestmark = pytest.mark.django_db

MAX_LENGTH = UserProfileRoutingKey.KEY_MAX_LENGTH


def test_generate_routing_key_kebab_cases_the_display_name():
    key = generate_routing_key("Jane Doe", MAX_LENGTH)
    base, suffix = key.rsplit("-", 1)
    assert base == "jane-doe"
    assert len(suffix) == ROUTING_KEY_SUFFIX_LENGTH


def test_generate_routing_key_is_unique_per_call():
    """Two users with the same display name get different keys."""
    keys = {generate_routing_key("Jane Doe", MAX_LENGTH) for _ in range(50)}
    assert len(keys) > 1


@pytest.mark.parametrize(
    "display_name",
    ["", None, "日本語", "!!!", "   "],
)
def test_generate_routing_key_falls_back_when_name_has_no_slug(display_name):
    """A name that slugifies to nothing still yields a usable key."""
    key = generate_routing_key(display_name, MAX_LENGTH)
    base, suffix = key.rsplit("-", 1)
    assert base == ROUTING_KEY_FALLBACK_BASE
    assert suffix.isalnum()


def test_generate_routing_key_transliterates_accents():
    assert generate_routing_key("Zoë Müller", MAX_LENGTH).startswith("zoe-muller-")


def test_generate_routing_key_respects_max_length():
    key = generate_routing_key("A" * 200, MAX_LENGTH)
    assert len(key) <= MAX_LENGTH


def test_routing_key_base_drops_hyphen_left_by_truncation():
    """Truncating mid-word must not leave "jane--suffix"."""
    assert not routing_key_base("Jane Doe", len("jane")).endswith("-")


def test_generate_routing_key_cannot_collide_with_reserved_segment():
    """The suffix keeps a key off the reserved /users/me/ route."""
    assert generate_routing_key("me", MAX_LENGTH) != "me"


def test_mint_for_persists_a_key_pointing_at_the_user():
    user = baker.make("users.User", display_name="Jane Doe", image=None)
    key = UserProfileRoutingKey.objects.mint_for(user)
    assert key.user == user
    assert key.routing_key.startswith("jane-doe-")


def test_mint_for_appends_rather_than_replacing():
    """Old keys survive a rename so shared URLs keep resolving."""
    user = baker.make("users.User", display_name="Jane Doe", image=None)
    from_signup = user.profile_routing_keys.get()
    user.display_name = "Jane Smith"
    renamed = UserProfileRoutingKey.objects.mint_for(user)

    assert user.profile_routing_keys.count() == 2
    assert user.profile_routing_keys.latest() == renamed
    assert UserProfileRoutingKey.objects.filter(pk=from_signup.pk).exists()


def test_mint_for_retries_past_a_taken_key(monkeypatch):
    """A suffix collision retries instead of raising."""
    user = baker.make("users.User", display_name="Jane Doe", image=None)
    taken = UserProfileRoutingKey.objects.create(routing_key="jane-doe-aaaa", user=user)

    keys = iter(["jane-doe-aaaa", "jane-doe-bbbb"])
    monkeypatch.setattr(
        "users.models.generate_routing_key", lambda *args, **kwargs: next(keys)
    )

    minted = UserProfileRoutingKey.objects.mint_for(user)
    assert minted.routing_key == "jane-doe-bbbb"
    assert minted.pk != taken.pk


def test_mint_for_raises_when_every_attempt_collides(monkeypatch):
    user = baker.make("users.User", display_name="Jane Doe", image=None)
    UserProfileRoutingKey.objects.create(routing_key="jane-doe-aaaa", user=user)
    monkeypatch.setattr(
        "users.models.generate_routing_key", lambda *args, **kwargs: "jane-doe-aaaa"
    )

    with pytest.raises(RuntimeError):
        UserProfileRoutingKey.objects.mint_for(user)


def test_new_user_is_given_a_routing_key():
    user = baker.make("users.User", display_name="Jane Doe", image=None)
    assert user.profile_routing_keys.get().routing_key.startswith("jane-doe-")


def test_user_created_through_the_manager_is_given_a_routing_key():
    """Signup goes through create_user(), not the model constructor."""
    user = User.objects.create_user(email="jane@example.com", password="pw12345678")
    assert user.profile_routing_keys.count() == 1


def test_new_user_without_a_display_name_is_given_a_fallback_key():
    """Email signup has no name yet, but still needs a public URL."""
    user = baker.make("users.User", display_name=None, image=None)
    key = user.profile_routing_keys.get().routing_key
    assert key.startswith(f"{ROUTING_KEY_FALLBACK_BASE}-")


def test_saving_an_existing_user_does_not_mint_another_key():
    """Only creation mints here; renames are handled at their own call site."""
    user = baker.make("users.User", display_name="Jane Doe", image=None)
    user.display_name = "Jane Smith"
    user.save()
    assert user.profile_routing_keys.count() == 1


def test_loading_a_fixture_does_not_mint_a_key():
    """loaddata sends raw=True, where side effects have to stay out."""
    user = baker.make("users.User", display_name="Jane Doe", image=None)
    post_save.send(sender=User, instance=user, created=True, raw=True)
    assert user.profile_routing_keys.count() == 1


def test_sync_for_keeps_the_current_key_when_the_name_is_unchanged():
    user = baker.make("users.User", display_name="Jane Doe", image=None)
    existing = user.profile_routing_keys.get()
    assert UserProfileRoutingKey.objects.sync_for(user) == existing
    assert user.profile_routing_keys.count() == 1


def test_sync_for_ignores_cosmetic_edits_to_the_name():
    """Extra whitespace slugifies the same, so the public URL should not move."""
    user = baker.make("users.User", display_name="Jane Doe", image=None)
    user.display_name = "  Jane   Doe  "
    UserProfileRoutingKey.objects.sync_for(user)
    assert user.profile_routing_keys.count() == 1


def test_sync_for_mints_when_the_name_changes():
    user = baker.make("users.User", display_name="Jane Doe", image=None)
    user.display_name = "Jane Smith"
    minted = UserProfileRoutingKey.objects.sync_for(user)

    assert minted.routing_key.startswith("jane-smith-")
    assert user.profile_routing_keys.count() == 2
    assert user.profile_routing_keys.latest() == minted


def test_sync_for_mints_when_the_user_has_no_key():
    user = baker.make("users.User", display_name="Jane Doe", image=None)
    user.profile_routing_keys.all().delete()
    assert UserProfileRoutingKey.objects.sync_for(user).routing_key.startswith(
        "jane-doe-"
    )


def social_account(user, provider="github", **extra_data):
    """Link a social account, triggering import_social_profile_data.

    No avatar_url/picture in extra_data, so the signal skips the image
    download and the test needs no HTTP mocking.
    """
    return baker.make(
        "socialaccount.SocialAccount",
        user=user,
        provider=provider,
        uid=f"uid-{provider}-{user.pk}",
        extra_data=extra_data,
    )


def test_social_signup_replaces_the_placeholder_key_with_a_named_one():
    """A GitHub signup should not be stuck on "user-..." forever."""
    user = baker.make("users.User", display_name=None, image=None)
    placeholder = user.profile_routing_keys.get()
    assert placeholder.base == ROUTING_KEY_FALLBACK_BASE

    social_account(user, name="Jane Doe", login="janedoe")

    user.refresh_from_db()
    assert user.display_name == "Jane Doe"
    assert user.profile_routing_keys.count() == 2
    assert user.profile_routing_keys.latest().routing_key.startswith("jane-doe-")


def test_social_signup_without_a_name_keeps_the_placeholder_key():
    user = baker.make("users.User", display_name=None, image=None)
    social_account(user, login="janedoe")
    assert user.profile_routing_keys.count() == 1


def test_linking_a_second_provider_does_not_mint_again():
    """Same name from a second provider means the same base: no new URL."""
    user = baker.make("users.User", display_name=None, image=None)
    social_account(user, provider="github", name="Jane Doe", login="janedoe")
    social_account(user, provider="google", name="Jane Doe")

    assert user.profile_routing_keys.count() == 2
    assert user.profile_routing_keys.latest().routing_key.startswith("jane-doe-")


def test_to_v3_profile_dict_does_not_link_by_default():
    """Contributor lists mix these dicts with account-less CommitAuthor ones,
    so linking is opt-in per call site."""
    user = baker.make("users.User", display_name="Jane Doe", image=None)
    assert user.to_v3_profile_dict()["profile_url"] is None


def test_to_v3_profile_dict_links_when_asked():
    user = baker.make("users.User", display_name="Jane Doe", image=None)
    profile = user.to_v3_profile_dict(link_profile=True)
    assert profile["profile_url"] == user.get_absolute_url()
    assert profile["profile_url"].startswith("/users/jane-doe-")


def test_to_v3_profile_dict_never_links_a_deactivated_account():
    """Their profile 404s, so a link would be broken."""
    user = baker.make(
        "users.User", display_name="Jane Doe", image=None, is_active=False
    )
    assert user.to_v3_profile_dict(link_profile=True)["profile_url"] is None


def test_profile_url_property_links_an_active_user():
    """Templates receiving a User directly (the v3 posts list) read this."""
    user = baker.make("users.User", display_name="Jane Doe", image=None)
    assert user.profile_url == user.get_absolute_url()


def test_profile_url_property_is_none_for_a_deactivated_user():
    user = baker.make(
        "users.User", display_name="Jane Doe", image=None, is_active=False
    )
    assert user.profile_url is None
