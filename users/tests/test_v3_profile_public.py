import pytest
import waffle.testutils
from model_bakery import baker

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
    """A profile with no content is the bio card alone: every other section is
    left out entirely rather than rendered as an empty shell."""
    with tp.login(user):
        response = tp.get("profile-account")
    content = response.content.decode()
    assert "user-profile__bio" in content
    for section_class in (
        "user-profile__achievements",
        "user-profile__badges",
        "user-profile__github",
        "user-profile__mailing-list",
        "user-profile__posts",
    ):
        assert section_class not in content


@waffle.testutils.override_flag("v3", active=True)
def test_own_profile_header_buttons_have_edit_but_no_share(user, tp):
    """Owners get Edit Profile where visitors get Share."""
    with tp.login(user):
        response = tp.get("profile-account")
    buttons = {link["label"]: link["url"] for link in response.context["top_links"]}
    assert "Share" not in buttons
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
    """/users/<pk>/ is readable by anonymous visitors and renders the profile
    it addresses, not the request user's."""
    response = tp.get("profile-user", pk=other_user.pk)
    tp.response_200(response)
    assert response.context["profile_user"] == other_user
    assert response.context["user_info"]["user_name"] == other_user.display_name


@waffle.testutils.override_flag("v3", active=True)
def test_profile_user_route_shows_share_to_a_visitor(user, other_user, tp):
    """A visitor -- signed in or not -- gets the Share button, never the
    owner's edit affordance."""
    with tp.login(user):
        response = tp.get("profile-user", pk=other_user.pk)
    labels = [link["label"] for link in response.context["top_links"]]
    assert "Share" in labels
    assert "Edit Profile" not in labels


@waffle.testutils.override_flag("v3", active=True)
def test_profile_user_route_shows_edit_to_the_owner(user, tp):
    """Reaching your own profile by its public URL still offers Edit Profile:
    the button follows who is looking, not which route was used."""
    with tp.login(user):
        response = tp.get("profile-user", pk=user.pk)
    labels = [link["label"] for link in response.context["top_links"]]
    assert "Edit Profile" in labels
    assert "Share" not in labels


@waffle.testutils.override_flag("v3", active=True)
def test_profile_user_route_404s_for_deactivated_account(other_user, tp):
    """Account deletion deactivates the user; the public page must stop
    resolving rather than keep serving their profile."""
    other_user.is_active = False
    other_user.save(update_fields=["is_active"])
    tp.response_404(tp.get("profile-user", pk=other_user.pk))


@waffle.testutils.override_flag("v3", active=False)
def test_profile_user_route_404s_when_v3_flag_is_off(other_user, tp):
    """The page exists only in v3; there is no legacy template to fall back
    to."""
    tp.response_404(tp.get("profile-user", pk=other_user.pk))


@waffle.testutils.override_flag("v3", active=True)
def test_profile_user_route_honours_the_hide_public_role_opt_out(user, tp):
    """`public_role` deliberately ignores the opt-out so owners keep seeing
    their own role; a visitor must get `role`, which honours it, or the public
    page publishes the role the opt-out exists to withhold."""
    user.internal_role = "cto"
    user.hide_public_role = True
    user.save(update_fields=["internal_role", "hide_public_role"])
    assert user.public_role, "the opt-out should be hiding a role that exists"

    visitor_view = tp.get("profile-user", pk=user.pk)
    assert visitor_view.context["user_info"]["role"] == ""

    with tp.login(user):
        own_view = tp.get("profile-user", pk=user.pk)
    assert own_view.context["user_info"]["role"] == user.public_role
