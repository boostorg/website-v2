import uuid
from datetime import timedelta

import pytest
import waffle.testutils
from django.utils import timezone
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
def test_v3_edit_page_shows_users_commit_emails(user, tp):
    # created first and alphabetically first, so both insertion order and
    # plain email order would wrongly put it ahead of the verified one
    pending = baker.make(
        "libraries.CommitAuthorEmail",
        email="a-pending@example.com",
        claim_verified=False,
        claim_hash=uuid.uuid4(),
        claim_hash_expiration=timezone.now() + timedelta(days=1),
        claimed_by=user,
    )
    verified = baker.make(
        "libraries.CommitAuthorEmail",
        email="z-verified@example.com",
        claim_verified=True,
        claimed_by=user,
    )
    other_users_email = baker.make(
        "libraries.CommitAuthorEmail",
        claim_verified=True,
        claimed_by=baker.make("users.User"),
    )
    # a withdrawn ask leaves no claim_hash; such a row is not a claim and
    # must not render (its withdraw button would only 404)
    withdrawn = baker.make(
        "libraries.CommitAuthorEmail",
        claim_verified=False,
        claim_hash=None,
        claimed_by=user,
    )
    # an expired ask is never cleared, just never shown; its address is
    # simply claimable again
    expired = baker.make(
        "libraries.CommitAuthorEmail",
        claim_verified=False,
        claim_hash=uuid.uuid4(),
        claim_hash_expiration=timezone.now() - timedelta(hours=1),
        claimed_by=user,
    )

    with tp.login(user):
        response = tp.get(f"{tp.reverse('profile-account')}?edit=true")
        tp.response_200(response)
        commit_email_addresses = response.context["commit_email_addresses"]

    # verified emails always render before pending ones
    assert list(commit_email_addresses) == [verified, pending]
    assert other_users_email not in commit_email_addresses
    assert withdrawn not in commit_email_addresses
    assert expired not in commit_email_addresses


@waffle.testutils.override_flag("v3", active=False)
def test_legacy_profile_lists_author_bound_emails(user, tp):
    """With the flag off the pre-v3 keying is intact: the profile lists
    every email of authors bound to the user (the legacy ask flow binds
    author.user at ask time), and claimed_by plays no part."""
    bound = baker.make(
        "libraries.CommitAuthorEmail",
        email="bound@example.com",
        claim_verified=False,
        claim_hash=uuid.uuid4(),
        claim_hash_expiration=timezone.now() + timedelta(days=1),
    )
    bound.author.user = user
    bound.author.save()
    sibling = baker.make(
        "libraries.CommitAuthorEmail",
        email="sibling@example.com",
        author=bound.author,
        claim_verified=True,
    )
    claimed_only = baker.make(
        "libraries.CommitAuthorEmail",
        email="claimed-only@example.com",
        claim_verified=False,
        claim_hash=uuid.uuid4(),
        claim_hash_expiration=timezone.now() + timedelta(days=1),
        claimed_by=user,
    )

    with tp.login(user):
        response = tp.get(tp.reverse("profile-account"))
        tp.response_200(response)
        commit_email_addresses = response.context["commit_email_addresses"]

    assert set(commit_email_addresses) == {bound, sibling}
    assert claimed_only not in commit_email_addresses


@waffle.testutils.override_flag("v3", active=True)
def test_v3_edit_page_commit_email_forms_carry_csrf_token(user, tp):
    """The card is included with `{% include ... only %}`, which drops the
    page context; csrf_token must be forwarded explicitly or every form in
    the card 403s on submit."""
    baker.make(
        "libraries.CommitAuthorEmail",
        claim_verified=False,
        claim_hash=uuid.uuid4(),
        claim_hash_expiration=timezone.now() + timedelta(days=1),
        claimed_by=user,
    )

    with tp.login(user):
        response = tp.get(f"{tp.reverse('profile-account')}?edit=true")
        tp.response_200(response)

    content = response.content.decode()
    card_body = content[content.find("commit-email-card-body") :]
    card_body = card_body[: card_body.find("+ Add Another")]
    # resend, delete, extra-row template, no-JS add row; each form must carry
    # its own csrf token, not just contribute to a page-wide count (the base
    # add row is only rendered when the user has no commit emails)
    forms = card_body.split("<form")[1:]
    assert len(forms) == 4
    for form_markup in forms:
        form_end = form_markup.find("</form>")
        assert form_end != -1
        assert "csrfmiddlewaretoken" in form_markup[:form_end]


def _commit_email_noscript(response):
    """The card body's <noscript> block - the only one inside the card."""
    body = response.content.decode()
    body = body[body.find("commit-email-card-body") :]
    start = body.find("<noscript>")
    return body[start : body.find("</noscript>", start)]


@waffle.testutils.override_flag("v3", active=True)
def test_v3_edit_page_commit_email_no_js_fallback(user, tp):
    """ "+ Add Another" appends rows through Alpine, so with JS off it is
    hidden and a plain add row stands in for it - but not when the
    conditional base add row is already rendering one."""
    with tp.login(user):
        no_emails = tp.get(f"{tp.reverse('profile-account')}?edit=true")
        baker.make("libraries.CommitAuthorEmail", claimed_by=user, claim_verified=True)
        with_email = tp.get(f"{tp.reverse('profile-account')}?edit=true")
    tp.response_200(no_emails)
    tp.response_200(with_email)

    for response in (no_emails, with_email):
        assert ".commit-email__add-another { display: none; }" in (
            _commit_email_noscript(response)
        )

    # the base add row already covers the empty case; no second field for it
    assert "commit-email__add-row" not in _commit_email_noscript(no_emails)
    assert _commit_email_noscript(with_email).count("commit-email__add-row") == 1


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
def test_v3_update_details_unchecks_omitted_toggles(user, tp):
    """The detail toggles are plain checkboxes, so an omitted key means the box
    was unchecked; the saved field must reset to False rather than keep its old
    True value."""
    user.indicate_last_login_method = True
    user.is_commit_author_name_overridden = True
    user.save()
    with tp.login(user):
        response = tp.post(
            f"{tp.reverse('profile-account')}?edit=true",
            data={
                "v3_update_details": "true",
                "username": user.display_name,
                "country": "",
            },
        )
        assert response.status_code == 302
    user.refresh_from_db()
    assert user.indicate_last_login_method is False
    assert user.is_commit_author_name_overridden is False


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
    """Only the details section is submitted, so hide_github (owned by a
    different section's form) is absent from the POST. A validation failure
    here must not blank out that other section's displayed state."""
    baker.make("users.User", display_name="taken-name")
    user.hide_github_activity = True
    user.save()
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
        assert form["hide_github"].value() is True
    user.refresh_from_db()
    assert user.display_name != "taken-name"


@waffle.testutils.override_flag("v3", active=True)
def test_v3_update_profile_redirect_flags_saved_section(user, tp):
    """The redirect after a successful save carries which section was saved,
    so that section's submit button can render a "Changes Saved" state
    instead of the legacy toast."""
    with tp.login(user):
        response = tp.post(
            f"{tp.reverse('profile-account')}?edit=true",
            data={"v3_update_profile": "true", "hide_github": "on"},
        )
        assert response.status_code == 302
        assert response.url == (
            f"{tp.reverse('profile-account')}?edit=true&saved=v3_update_profile"
        )


@waffle.testutils.override_flag("v3", active=True)
def test_v3_update_profile_ajax_save_returns_json_without_redirect(user, tp):
    """A fetch-based submit (see createSectionForm in user_profile_edit.html)
    gets a JSON response instead of a redirect, so the button can flip to
    "Changes Saved" without a full-page navigation."""
    with tp.login(user):
        response = tp.post(
            f"{tp.reverse('profile-account')}?edit=true",
            data={"v3_update_profile": "true", "hide_github": "on"},
            extra={"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"},
        )
        assert response.status_code == 200
        assert response["Content-Type"] == "application/json"
        assert response.json() == {"saved": "v3_update_profile"}
    user.refresh_from_db()
    assert user.hide_github_activity is True


@waffle.testutils.override_flag("v3", active=True)
def test_v3_edit_page_marks_only_the_saved_section(user, tp):
    with tp.login(user):
        response = tp.get(
            f"{tp.reverse('profile-account')}?edit=true&saved=v3_update_details"
        )
        tp.response_200(response)
        saved_sections = response.context["saved_sections"]
        assert saved_sections["v3_update_details"] is True
        assert saved_sections["v3_update_profile"] is False
        assert saved_sections["v3_update_email_preferences"] is False


@waffle.testutils.override_flag("v3", active=True)
def test_v3_edit_page_no_section_saved_by_default(user, tp):
    with tp.login(user):
        response = tp.get(f"{tp.reverse('profile-account')}?edit=true")
        tp.response_200(response)
        assert not any(response.context["saved_sections"].values())


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
