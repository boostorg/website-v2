import pytest
import waffle.testutils
from model_bakery import baker

from users.models import UserProfileRoutingKey

pytestmark = pytest.mark.django_db


@pytest.fixture
def other_user(db):
    """A second user, to be looked at rather than logged in as."""
    return baker.make(
        "users.User",
        email="other@example.com",
        display_name="Other User",
        image=None,
    )


@waffle.testutils.override_flag("v3", active=True)
def test_public_profile_renders_header_from_real_user_data(user, tp):
    """The header shows the user's real display name and join year."""
    with tp.login(user):
        response = tp.get("profile-account")
    tp.response_200(response)
    content = response.content.decode()
    assert user.display_name in content
    assert f"Member Since {user.year_joined}" in content


@waffle.testutils.override_flag("v3", active=True)
def test_public_profile_shows_bio_empty_state_when_no_bio(user, tp):
    """With no bio, the bio card renders its empty state rather than being
    hidden."""
    with tp.login(user):
        response = tp.get("profile-account")
    content = response.content.decode()
    assert "This user hasn't added a bio yet." in content


@waffle.testutils.override_flag("v3", active=True)
def test_public_profile_renders_biography_as_markdown(user, tp):
    """A stored biography replaces the empty state and is rendered as Markdown
    rather than escaped into the page as its raw source."""
    user.biography = "I maintain **Beast** and work on HTTP."
    user.save(update_fields=["biography"])
    with tp.login(user):
        response = tp.get("profile-account")
    content = response.content.decode()
    assert "<strong>Beast</strong>" in content
    assert "**Beast**" not in content
    assert "This user hasn't added a bio yet." not in content


@waffle.testutils.override_flag("v3", active=True)
def test_public_profile_hides_every_section_with_no_data(user, tp):
    """A profile with no content leaves its data sections out entirely rather
    than rendering them as empty shells.

    The two recognition cards are the documented exceptions on the owner's own
    page: their empty states carry the only CTAs that open the badge and
    achievement dialogs, so they render with nothing held - see
    `badges.tests.test_profile.test_own_profile_page_renders_without_badges`
    and `users.tests.test_profile_dialogs`.
    """
    with tp.login(user):
        response = tp.get("profile-account")
    content = response.content.decode()
    assert "user-profile__bio" in content
    for section_class in (
        "user-profile__github",
        "user-profile__mailing-list",
        "user-profile__posts",
    ):
        assert section_class not in content


@waffle.testutils.override_flag("v3", active=True)
def test_own_profile_header_buttons_have_edit_but_no_share(user, tp):
    """Owners get Edit Profile where visitors get Share Profile."""
    with tp.login(user):
        response = tp.get("profile-account")
    buttons = {link["label"]: link["url"] for link in response.context["top_links"]}
    assert "Share Profile" not in buttons
    assert buttons["Edit Profile"] == f"{tp.reverse('profile-account')}?edit=true"


@waffle.testutils.override_flag("v3", active=True)
def test_public_profile_renders_only_populated_links(user, tp):
    """Only profile links with a value render, and email becomes a mailto:
    link while the rest link out to their stored URL."""
    user.profile_links = {
        "github": "https://github.com/example",
        "email": "person@example.com",
    }
    user.save()
    with tp.login(user):
        response = tp.get("profile-account")
    buttons = {link["label"]: link["url"] for link in response.context["top_links"]}
    assert buttons["GitHub"] == "https://github.com/example"
    assert buttons["Email"] == "mailto:person@example.com"
    # Website and Slack were not set, so their buttons are absent.
    assert "Website" not in buttons
    assert "Chat on Slack" not in buttons


@waffle.testutils.override_flag("v3", active=True)
def test_public_profile_omits_link_with_unsafe_scheme(user, tp):
    """A stored link with a non-http(s) scheme (e.g. javascript:) is dropped
    rather than rendered into an href, while a scheme-less value is coerced
    to https."""
    user.profile_links = {
        "website": "javascript:alert(document.cookie)",
        "github": "github.com/example",
    }
    user.save()
    with tp.login(user):
        response = tp.get("profile-account")
    buttons = {link["label"]: link["url"] for link in response.context["top_links"]}
    assert "Website" not in buttons
    assert buttons["GitHub"] == "https://github.com/example"
    assert "javascript:" not in response.content.decode()


@waffle.testutils.override_flag("v3", active=True)
def test_profile_user_route_renders_another_users_profile(other_user, tp):
    """/users/<routing-key>/ is readable by anonymous visitors and renders the profile
    it addresses, not the request user's."""
    response = tp.get(
        "profile-user", routing_key=other_user.profile_routing_key.routing_key
    )
    tp.response_200(response)
    assert response.context["profile_user"] == other_user
    assert response.context["user_info"]["user_name"] == other_user.display_name


@waffle.testutils.override_flag("v3", active=True)
def test_profile_user_route_shows_share_to_a_visitor(user, other_user, tp):
    """A visitor -- signed in or not -- gets the Share Profile button, never
    the owner's edit affordance."""
    with tp.login(user):
        response = tp.get(
            "profile-user", routing_key=other_user.profile_routing_key.routing_key
        )
    labels = [link["label"] for link in response.context["top_links"]]
    assert "Share Profile" in labels
    assert "Edit Profile" not in labels


@waffle.testutils.override_flag("v3", active=True)
def test_profile_user_route_shows_edit_to_the_owner(user, tp):
    """Reaching your own profile by its public URL still offers Edit Profile:
    the button follows who is looking, not which route was used."""
    with tp.login(user):
        response = tp.get(
            "profile-user", routing_key=user.profile_routing_key.routing_key
        )
    labels = [link["label"] for link in response.context["top_links"]]
    assert "Edit Profile" in labels
    assert "Share Profile" not in labels


@waffle.testutils.override_flag("v3", active=True)
def test_profile_user_route_404s_for_deactivated_account(other_user, tp):
    """Account deletion deactivates the user; the public page must stop
    resolving rather than keep serving their profile."""
    other_user.is_active = False
    other_user.save(update_fields=["is_active"])
    tp.response_404(
        tp.get("profile-user", routing_key=other_user.profile_routing_key.routing_key)
    )


@waffle.testutils.override_flag("v3", active=False)
def test_profile_user_route_404s_when_v3_flag_is_off(other_user, tp):
    """The page exists only in v3; there is no legacy template to fall back
    to."""
    tp.response_404(
        tp.get("profile-user", routing_key=other_user.profile_routing_key.routing_key)
    )


@waffle.testutils.override_flag("v3", active=True)
def test_profile_user_route_honours_the_hide_public_role_opt_out(user, tp):
    """`public_role` deliberately ignores the opt-out so owners keep seeing
    their own role; a visitor must get `role`, which honours it, or the public
    page publishes the role the opt-out exists to withhold."""
    user.internal_role = "cto"
    user.hide_public_role = True
    user.save(update_fields=["internal_role", "hide_public_role"])
    assert user.public_role, "the opt-out should be hiding a role that exists"

    visitor_view = tp.get(
        "profile-user", routing_key=user.profile_routing_key.routing_key
    )
    assert visitor_view.context["user_info"]["role"] == ""

    with tp.login(user):
        own_view = tp.get(
            "profile-user", routing_key=user.profile_routing_key.routing_key
        )
    assert own_view.context["user_info"]["role"] == user.public_role


@waffle.testutils.override_flag("v3", active=True)
def test_profile_user_route_resolves_the_canonical_key(other_user, tp):
    """The URL a profile is linked by is the user's newest key."""
    key = other_user.profile_routing_key.routing_key
    response = tp.get("profile-user", routing_key=key)
    tp.response_200(response)
    assert response.context["profile_user"] == other_user
    assert other_user.get_absolute_url() == f"/users/{key}/"


@waffle.testutils.override_flag("v3", active=True)
def test_profile_user_route_redirects_a_superseded_key(other_user, tp):
    """A shared link keeps working after a rename, pointing at the new URL."""
    old_key = other_user.profile_routing_key.routing_key
    other_user.display_name = "Renamed User"
    other_user.save()
    new_key = UserProfileRoutingKey.objects.sync_for(other_user).routing_key
    assert new_key != old_key

    response = tp.get("profile-user", routing_key=old_key)
    assert response.status_code == 301
    assert response["Location"] == f"/users/{new_key}/"


@waffle.testutils.override_flag("v3", active=True)
def test_profile_user_route_404s_for_an_unknown_key(tp):
    tp.response_404(tp.get("profile-user", routing_key="nobody-0000"))


@waffle.testutils.override_flag("v3", active=True)
def test_profile_user_route_does_not_shadow_the_literal_users_routes(user, tp):
    """The slug converter matches "me" and "avatar", so those must resolve to
    their own views rather than to a profile lookup."""
    with tp.login(user):
        tp.response_200(tp.get("profile-account"))
    assert tp.reverse("user-avatar") == "/users/avatar/"


@waffle.testutils.override_flag("v3", active=True)
def test_share_button_carries_the_profile_url(other_user, tp):
    """Share copies the profile URL client-side, so the href has to be the real
    URL rather than "#" -- which also leaves a working link with JS off."""
    response = tp.get(
        "profile-user", routing_key=other_user.profile_routing_key.routing_key
    )
    share = [link for link in response.context["top_links"] if link["label"] == "Share"]
    assert share, "a visitor should see the Share button"
    assert share[0]["url"] == other_user.get_absolute_url()
    assert share[0]["extra_classes"] == "js-copy-profile-url"

    content = response.content.decode()
    assert f'href="{other_user.get_absolute_url()}"' in content
    assert "js-copy-profile-url" in content
    assert "share-profile.js" in content


@waffle.testutils.override_flag("v3", active=True)
def test_owner_gets_edit_profile_instead_of_share(user, tp):
    """The trailing button follows who is looking, so the owner has nothing to
    copy here."""
    with tp.login(user):
        response = tp.get(
            "profile-user", routing_key=user.profile_routing_key.routing_key
        )
    labels = [link["label"] for link in response.context["top_links"]]
    assert "Edit Profile" in labels
    assert "Share" not in labels
