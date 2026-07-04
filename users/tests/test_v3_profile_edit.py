import pytest
import waffle.testutils
from model_bakery import baker

pytestmark = pytest.mark.django_db


@waffle.testutils.override_flag("v3", active=True)
def test_v3_update_profile_post_requires_login(tp):
    response = tp.post(
        f"{tp.reverse('profile-account')}?edit=true",
        data={"v3_update_profile": "true", "hide_github": "on"},
    )
    tp.response_302(response)
    assert "login" in response.url


@waffle.testutils.override_flag("v3", active=True)
def test_v3_get_profile_page_requires_login(tp):
    """V3Mixin renders for every HTTP method once the v3 flag is active, so
    it never reaches LoginRequiredMixin's check on its own; this view must
    enforce login itself for GET too, not just for the POST handlers."""
    response = tp.get(tp.reverse("profile-account"))
    tp.response_302(response)
    assert "login" in response.url


@waffle.testutils.override_flag("v3", active=True)
def test_v3_get_edit_page_requires_login(tp):
    response = tp.get(f"{tp.reverse('profile-account')}?edit=true")
    tp.response_302(response)
    assert "login" in response.url


@waffle.testutils.override_flag("v3", active=True)
def test_v3_update_profile_saves_despite_overlong_scaffolding_field(user, tp):
    """tagline/bio share the Profile <form> with the visibility toggles but
    have no save handler yet; an overlong tagline (past its max_length)
    must not block saving the toggles that are ready."""
    with tp.login(user):
        response = tp.post(
            f"{tp.reverse('profile-account')}?edit=true",
            data={
                "v3_update_profile": "true",
                "hide_github": "on",
                "tagline": "x" * 100,
            },
        )
        assert response.status_code == 302
    user.refresh_from_db()
    assert user.hide_github_activity is True


@waffle.testutils.override_flag("v3", active=True)
def test_v3_edit_page_shows_current_values(user, tp):
    user.hide_github_activity = True
    user.country = "US"
    user.save()
    with tp.login(user):
        response = tp.get(f"{tp.reverse('profile-account')}?edit=true")
        tp.response_200(response)
        form = response.context["user_profile_form"]
        assert form.initial["username"] == user.display_name
        assert form.initial["hide_github"] is True
        assert form.initial["country"] == "US"


@waffle.testutils.override_flag("v3", active=True)
def test_v3_update_profile_saves_visibility_toggles(user, tp):
    with tp.login(user):
        response = tp.post(
            f"{tp.reverse('profile-account')}?edit=true",
            data={
                "v3_update_profile": "true",
                "hide_github": "on",
                "hide_ml": "on",
            },
        )
        assert response.status_code == 302
    user.refresh_from_db()
    assert user.hide_github_activity is True
    assert user.hide_mailing_list_activity is True
    assert user.hide_badges is False


@waffle.testutils.override_flag("v3", active=True)
def test_v3_update_details_saves_account_fields(user, tp):
    with tp.login(user):
        response = tp.post(
            f"{tp.reverse('profile-account')}?edit=true",
            data={
                "v3_update_details": "true",
                "username": "newusername",
                "country": "US",
                "indicate_last_login_method": "on",
                "override_commit_author_name": "on",
            },
        )
        assert response.status_code == 302
    user.refresh_from_db()
    assert user.display_name == "newusername"
    assert str(user.country) == "US"
    assert user.indicate_last_login_method is True
    assert user.is_commit_author_name_overridden is True


@waffle.testutils.override_flag("v3", active=True)
def test_v3_update_details_blank_country_clears_it(user, tp):
    user.country = "US"
    user.save()
    with tp.login(user):
        tp.post(
            f"{tp.reverse('profile-account')}?edit=true",
            data={
                "v3_update_details": "true",
                "username": user.display_name,
                "country": "",
            },
        )
    user.refresh_from_db()
    assert str(user.country) == ""


@waffle.testutils.override_flag("v3", active=True)
def test_v3_update_details_duplicate_username_shows_inline_error(user, tp):
    baker.make("users.User", display_name="taken-name")
    with tp.login(user):
        response = tp.post(
            f"{tp.reverse('profile-account')}?edit=true",
            data={
                "v3_update_details": "true",
                "username": "taken-name",
                "country": "",
            },
        )
        tp.response_200(response)
        form = response.context["user_profile_form"]
        assert "This username is already taken" in form.errors["username"]
    user.refresh_from_db()
    assert user.display_name != "taken-name"


@waffle.testutils.override_flag("v3", active=True)
def test_v3_update_email_preferences_saves(user, tp):
    with tp.login(user):
        response = tp.post(
            f"{tp.reverse('profile-account')}?edit=true",
            data={
                "v3_update_email_preferences": "true",
                "allow_notification_own_news_approved": ["blogpost", "news"],
                "allow_notification_others_news_posted": ["link"],
            },
        )
        assert response.status_code == 302
    user.preferences.refresh_from_db()
    # The user's default preference for "own news approved" is the wildcard
    # (all news types, including "poll"). The v3 page has no checkbox for
    # "poll", so it must be preserved rather than dropped by this save.
    assert sorted(user.preferences.allow_notification_own_news_approved) == [
        "blogpost",
        "news",
        "poll",
    ]
    assert user.preferences.allow_notification_others_news_posted == ["link"]


@waffle.testutils.override_flag("v3", active=True)
def test_v3_update_email_preferences_preserves_unlisted_news_types(user, tp):
    """The v3 page only renders checkboxes for a subset of news types
    (blogpost/link/news/video). Saving it must not silently unsubscribe the
    user from types the page doesn't show, like "poll"."""
    user.preferences.allow_notification_own_news_approved = ["poll"]
    user.preferences.allow_notification_others_news_posted = ["poll", "link"]
    user.preferences.save()
    with tp.login(user):
        response = tp.post(
            f"{tp.reverse('profile-account')}?edit=true",
            data={
                "v3_update_email_preferences": "true",
                "allow_notification_own_news_approved": ["blogpost"],
                "allow_notification_others_news_posted": ["link"],
            },
        )
        assert response.status_code == 302
    user.preferences.refresh_from_db()
    assert sorted(user.preferences.allow_notification_own_news_approved) == [
        "blogpost",
        "poll",
    ]
    assert sorted(user.preferences.allow_notification_others_news_posted) == [
        "link",
        "poll",
    ]
