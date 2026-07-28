import pytest
import waffle.testutils

pytestmark = pytest.mark.django_db


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
def test_public_profile_always_shows_achievements_and_badges(user, tp):
    """Achievements and Badges always render (with empty-state cards), while
    data-less sections (GitHub, mailing list, posts) are omitted."""
    with tp.login(user):
        response = tp.get("profile-account")
    content = response.content.decode()
    # Always present, with their empty states.
    assert "user-profile__achievements" in content
    assert "user-profile__badges" in content
    assert "No achievements earned yet." in content
    assert "Learn how achievements work" in content
    assert "No badges unlocked yet." in content
    assert "Learn how badges work" in content
    # Still hidden when they have no data.
    for section_class in (
        "user-profile__github",
        "user-profile__mailing-list",
        "user-profile__posts",
    ):
        assert section_class not in content


@waffle.testutils.override_flag("v3", active=True)
def test_public_profile_header_buttons_have_share_but_no_edit(user, tp):
    """The profile header buttons expose Share but none of the owner's edit
    affordances. (An Edit link may still appear in the global account nav,
    which is site chrome, not part of this view's controls.)"""
    with tp.login(user):
        response = tp.get("profile-account")
    labels = [link["label"] for link in response.context["top_links"]]
    assert "Share" in labels
    assert "Edit Profile" not in labels


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
