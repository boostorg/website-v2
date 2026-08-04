import pytest
from model_bakery import baker

from users.models import UserProfileRoutingKey
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
    first = UserProfileRoutingKey.objects.mint_for(user)
    user.display_name = "Jane Smith"
    second = UserProfileRoutingKey.objects.mint_for(user)

    assert user.profile_routing_keys.count() == 2
    assert user.profile_routing_keys.latest() == second
    assert UserProfileRoutingKey.objects.filter(pk=first.pk).exists()


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
