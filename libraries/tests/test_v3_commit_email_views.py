import uuid
from datetime import timedelta

import pytest
import waffle.testutils
from django.utils import timezone
from django.utils.formats import date_format
from model_bakery import baker

from ..models import CommitAuthorEmail

pytestmark = pytest.mark.django_db


def _unclaimed_commit_email(email="dev@example.com"):
    return baker.make(
        "libraries.CommitAuthorEmail",
        email=email,
        claim_verified=False,
    )


def _pending_claim(user, email="dev@example.com"):
    """An email mid-claim: verification requested by `user` (claimed_by +
    claim_hash set) but not yet confirmed - what ask_to_claim leaves
    behind. author.user is untouched until verification."""
    return baker.make(
        "libraries.CommitAuthorEmail",
        email=email,
        claim_verified=False,
        claim_hash=uuid.uuid4(),
        claim_hash_expiration=timezone.now() + timedelta(days=1),
        claimed_by=user,
    )


def _assert_refused_with_alert(tp, response):
    """A refused row action (withdraw/resend) reports the reason back through
    the card rather than 404ing: htmx silently drops a 404, and with JS off it
    is a dead-end error page, so either way the user was told nothing. The
    action itself is still refused - each caller asserts state is untouched.
    """
    tp.response_302(response)
    assert "ce_alert=" in response.url


def _verified_claim(user, email="dev@example.com"):
    """A completed claim - what verify_claim leaves behind."""
    commit_author_email = _pending_claim(user, email=email)
    commit_author_email.claim_verified = True
    commit_author_email.save()
    commit_author_email.author.user = user
    commit_author_email.author.save()
    return commit_author_email


# --- create (ask to claim) ---


def test_v3_commit_email_create_requires_login(tp):
    commit_author_email = _unclaimed_commit_email()
    response = tp.post(
        tp.reverse("v3-commit-author-email-create"),
        data={"commit_email": commit_author_email.email},
    )
    tp.response_302(response)
    assert "login" in response.url


@waffle.testutils.override_flag("v3", active=True)
def test_v3_commit_email_create_claims_and_sends_verification(user, tp, mailoutbox):
    commit_author_email = _unclaimed_commit_email()
    with tp.login(user):
        response = tp.post(
            tp.reverse("v3-commit-author-email-create"),
            data={"commit_email": commit_author_email.email},
        )
    tp.response_302(response)

    commit_author_email.refresh_from_db()
    assert commit_author_email.claimed_by == user
    assert commit_author_email.claim_verified is False
    assert commit_author_email.claim_hash is not None
    # asking is side-effect-free: public attribution is only bound at
    # verification
    assert commit_author_email.author.user is None
    assert len(mailoutbox) == 1
    assert commit_author_email.email in mailoutbox[0].to
    body = mailoutbox[0].body
    assert commit_author_email.email in body
    assert str(commit_author_email.claim_hash) in body
    assert "It expires in 1\xa0day." in body
    assert "only works while signed in to the account that requested it" in body
    assert "you can safely ignore this email" in body


@waffle.testutils.override_flag("v3", active=True)
def test_v3_commit_email_verification_email_names_the_requester(user, tp, mailoutbox):
    user.display_name = "Requesting User"
    user.save()
    commit_author_email = _unclaimed_commit_email()
    with tp.login(user):
        tp.post(
            tp.reverse("v3-commit-author-email-create"),
            data={"commit_email": commit_author_email.email},
        )
    assert "The user Requesting User has asked to link" in mailoutbox[0].body


def test_v3_commit_email_create_htmx_returns_updated_card(user, tp):
    commit_author_email = _unclaimed_commit_email()
    with tp.login(user):
        response = tp.post(
            tp.reverse("v3-commit-author-email-create"),
            data={"commit_email": commit_author_email.email},
            extra={"HTTP_HX_REQUEST": "true"},
        )
    tp.response_200(response)
    content = response.content.decode()
    assert commit_author_email.email in content
    # once the user has an email the base add row is dropped; a further email
    # is added through the "+ Add Another" (extra-row) flow
    # resend, withdraw, extra-row template
    assert content.count("<form") == 3
    # htmx parses swaps with DOMParser, where scripting is off, so a
    # <noscript> here would hide "+ Add Another" and add a row on a client
    # that plainly has JS - the fallback must not be in a swap at all
    assert "<noscript>" not in content


def test_v3_commit_email_create_htmx_invalid_shows_inline_error(user, tp):
    with tp.login(user):
        response = tp.post(
            tp.reverse("v3-commit-author-email-create"),
            data={"commit_email": "not-a-real-commit-author@example.com"},
            extra={"HTTP_HX_REQUEST": "true"},
        )
    tp.response_200(response)
    content = response.content.decode()
    assert "field--error" in content
    assert "Email address is not associated with any commits." in content
    assert "not-a-real-commit-author@example.com" in content


def test_v3_commit_email_create_own_verified_email_shows_own_account_error(user, tp):
    commit_author_email = _verified_claim(user)

    with tp.login(user):
        response = tp.post(
            tp.reverse("v3-commit-author-email-create"),
            data={"commit_email": commit_author_email.email},
            extra={"HTTP_HX_REQUEST": "true"},
        )
    tp.response_200(response)
    content = response.content.decode()
    assert "field--error" in content
    assert "This email address is already associated with your account." in content


def test_v3_commit_email_create_other_verified_email_shows_other_user_error(user, tp):
    other_user = baker.make("users.User")
    commit_author_email = _verified_claim(other_user)

    with tp.login(user):
        response = tp.post(
            tp.reverse("v3-commit-author-email-create"),
            data={"commit_email": commit_author_email.email},
            extra={"HTTP_HX_REQUEST": "true"},
        )
    tp.response_200(response)
    content = response.content.decode()
    assert "field--error" in content
    assert "already been claimed by another user" in content


def test_v3_commit_email_create_own_pending_claim_shows_pending_error(user, tp):
    commit_author_email = _pending_claim(user)

    with tp.login(user):
        response = tp.post(
            tp.reverse("v3-commit-author-email-create"),
            data={"commit_email": commit_author_email.email},
            extra={"HTTP_HX_REQUEST": "true"},
        )
    tp.response_200(response)
    content = response.content.decode()
    assert "field--error" in content
    assert "A verification email is already pending for this address." in content


def test_v3_commit_email_create_other_pending_claim_shows_pending_error(user, tp):
    other_user = baker.make("users.User")
    commit_author_email = _pending_claim(other_user)

    with tp.login(user):
        response = tp.post(
            tp.reverse("v3-commit-author-email-create"),
            data={"commit_email": commit_author_email.email},
            extra={"HTTP_HX_REQUEST": "true"},
        )
    tp.response_200(response)
    content = response.content.decode()
    assert "field--error" in content
    assert "verification pending by another user" in content


def test_v3_commit_email_create_expired_pending_claim_is_reclaimable(
    user, tp, mailoutbox
):
    other_user = baker.make("users.User")
    commit_author_email = _pending_claim(other_user)
    commit_author_email.claim_hash_expiration = timezone.now() - timedelta(hours=1)
    commit_author_email.save()

    with tp.login(user):
        response = tp.post(
            tp.reverse("v3-commit-author-email-create"),
            data={"commit_email": commit_author_email.email},
        )
    tp.response_302(response)
    commit_author_email.refresh_from_db()
    assert commit_author_email.claimed_by == user
    assert len(mailoutbox) == 1


def test_v3_commit_email_create_sync_bound_author_is_claimable(user, tp, mailoutbox):
    """An author bound only by the email/github matching heuristics (no
    verified claim, no claim_hash) must not dead-end the real owner;
    verification is what settles ownership."""
    other_user = baker.make("users.User")
    commit_author_email = _unclaimed_commit_email()
    commit_author_email.author.user = other_user
    commit_author_email.author.save()

    with tp.login(user):
        response = tp.post(
            tp.reverse("v3-commit-author-email-create"),
            data={"commit_email": commit_author_email.email},
        )
    tp.response_302(response)
    commit_author_email.refresh_from_db()
    assert commit_author_email.claimed_by == user
    # attribution is untouched until the claim is verified
    assert commit_author_email.author.user == other_user
    assert len(mailoutbox) == 1


def test_v3_commit_email_create_blocked_by_other_users_verified_sibling(user, tp):
    other_user = baker.make("users.User")
    verified = _verified_claim(other_user, email="verified@example.com")
    sibling = baker.make(
        "libraries.CommitAuthorEmail",
        email="sibling@example.com",
        author=verified.author,
        claim_verified=False,
    )

    with tp.login(user):
        response = tp.post(
            tp.reverse("v3-commit-author-email-create"),
            data={"commit_email": sibling.email},
            extra={"HTTP_HX_REQUEST": "true"},
        )
    tp.response_200(response)
    content = response.content.decode()
    assert "field--error" in content
    assert "already associated with another user" in content


def test_v3_commit_email_create_rejects_unknown_email(user, tp):
    with tp.login(user):
        response = tp.post(
            tp.reverse("v3-commit-author-email-create"),
            data={"commit_email": "not-a-real-commit-author@example.com"},
        )
    tp.response_302(response)
    assert not CommitAuthorEmail.objects.filter(
        email="not-a-real-commit-author@example.com"
    ).exists()


# --- withdraw (revoke a pending ask) ---


def test_v3_commit_email_withdraw_requires_login(tp):
    commit_author_email = _unclaimed_commit_email()
    response = tp.post(
        tp.reverse("v3-commit-author-email-withdraw", pk=commit_author_email.pk)
    )
    tp.response_302(response)
    assert "login" in response.url


def test_v3_commit_email_withdraw_reverts_pending_claim(user, tp):
    """The X on a pending row must be side-effect-free: the imported
    CommitAuthorEmail row survives and only this row's claim fields are
    cleared."""
    commit_author_email = _pending_claim(user)

    with tp.login(user):
        response = tp.post(
            tp.reverse("v3-commit-author-email-withdraw", pk=commit_author_email.pk)
        )
    tp.response_302(response)

    commit_author_email.refresh_from_db()
    assert commit_author_email.claim_hash is None
    assert commit_author_email.claimed_by is None
    assert commit_author_email.claim_verified is False
    assert commit_author_email.author.user is None


def test_v3_commit_email_withdraw_legacy_claim_unbinds_author(user, tp):
    """Rows claimed before the claimed_by field existed bound author.user at
    ask time (and the backfill set claimed_by=author.user); withdrawing one
    must also revert that legacy binding."""
    commit_author_email = _pending_claim(user)
    commit_author_email.author.user = user
    commit_author_email.author.save()

    with tp.login(user):
        response = tp.post(
            tp.reverse("v3-commit-author-email-withdraw", pk=commit_author_email.pk)
        )
    tp.response_302(response)
    commit_author_email.author.refresh_from_db()
    assert commit_author_email.author.user is None


def test_v3_commit_email_withdraw_legacy_claim_keeps_author_with_verified_sibling(
    user, tp
):
    verified = _verified_claim(user, email="verified@example.com")
    pending = baker.make(
        "libraries.CommitAuthorEmail",
        email="pending@example.com",
        author=verified.author,
        claim_verified=False,
        claim_hash=uuid.uuid4(),
        claim_hash_expiration=timezone.now() + timedelta(days=1),
        claimed_by=user,
    )

    with tp.login(user):
        response = tp.post(tp.reverse("v3-commit-author-email-withdraw", pk=pending.pk))
    tp.response_302(response)

    pending.refresh_from_db()
    assert pending.claim_hash is None
    pending.author.refresh_from_db()
    assert pending.author.user == user


def test_v3_commit_email_withdraw_legacy_claim_ignores_expired_sibling(user, tp):
    """Expired asks are never cleared, only ignored; a dead sibling token
    (even the claimant's own) must not keep the legacy binding alive."""
    expired = baker.make(
        "libraries.CommitAuthorEmail",
        email="expired@example.com",
        claim_verified=False,
        claim_hash=uuid.uuid4(),
        claim_hash_expiration=timezone.now() - timedelta(hours=1),
        claimed_by=user,
    )
    pending = baker.make(
        "libraries.CommitAuthorEmail",
        email="pending@example.com",
        author=expired.author,
        claim_verified=False,
        claim_hash=uuid.uuid4(),
        claim_hash_expiration=timezone.now() + timedelta(days=1),
        claimed_by=user,
    )
    pending.author.user = user
    pending.author.save()

    with tp.login(user):
        response = tp.post(tp.reverse("v3-commit-author-email-withdraw", pk=pending.pk))
    tp.response_302(response)

    pending.author.refresh_from_db()
    assert pending.author.user is None


def test_v3_commit_email_withdraw_legacy_claim_ignores_other_users_sibling(user, tp):
    """Another user's open ask on a sibling email never bound this author to
    the withdrawing claimant, so it must not preserve the claimant's legacy
    binding either."""
    other_user = baker.make("users.User")
    pending = _pending_claim(user)
    baker.make(
        "libraries.CommitAuthorEmail",
        email="theirs@example.com",
        author=pending.author,
        claim_verified=False,
        claim_hash=uuid.uuid4(),
        claim_hash_expiration=timezone.now() + timedelta(days=1),
        claimed_by=other_user,
    )
    pending.author.user = user
    pending.author.save()

    with tp.login(user):
        response = tp.post(tp.reverse("v3-commit-author-email-withdraw", pk=pending.pk))
    tp.response_302(response)

    pending.author.refresh_from_db()
    assert pending.author.user is None


def test_v3_commit_email_withdraw_does_not_unbind_sync_bound_author(user, tp):
    """Withdrawing a claim on an email whose author was bound to a different
    user by the matching heuristics must leave that binding alone."""
    other_user = baker.make("users.User")
    commit_author_email = _pending_claim(user)
    commit_author_email.author.user = other_user
    commit_author_email.author.save()

    with tp.login(user):
        response = tp.post(
            tp.reverse("v3-commit-author-email-withdraw", pk=commit_author_email.pk)
        )
    tp.response_302(response)
    commit_author_email.author.refresh_from_db()
    assert commit_author_email.author.user == other_user


def test_v3_commit_email_withdraw_refuses_verified_email(user, tp):
    commit_author_email = _verified_claim(user)

    with tp.login(user):
        response = tp.post(
            tp.reverse("v3-commit-author-email-withdraw", pk=commit_author_email.pk)
        )
    _assert_refused_with_alert(tp, response)
    commit_author_email.refresh_from_db()
    assert commit_author_email.claim_verified is True
    assert commit_author_email.author.user == user


def test_v3_commit_email_withdraw_refuses_email_without_open_ask(user, tp):
    """A bound author's other imported emails were never claimed; withdrawing
    one must be refused and leave everything alone."""
    verified = _verified_claim(user, email="verified@example.com")
    sibling = baker.make(
        "libraries.CommitAuthorEmail",
        email="never-asked@example.com",
        author=verified.author,
        claim_verified=False,
    )

    with tp.login(user):
        response = tp.post(tp.reverse("v3-commit-author-email-withdraw", pk=sibling.pk))
    _assert_refused_with_alert(tp, response)
    sibling.author.refresh_from_db()
    assert sibling.author.user == user


def test_v3_commit_email_withdraw_refuses_other_users_email(user, tp):
    other_user = baker.make("users.User")
    commit_author_email = _pending_claim(other_user)

    with tp.login(user):
        response = tp.post(
            tp.reverse("v3-commit-author-email-withdraw", pk=commit_author_email.pk)
        )
    _assert_refused_with_alert(tp, response)
    commit_author_email.refresh_from_db()
    assert commit_author_email.claim_hash is not None
    assert commit_author_email.claimed_by == other_user


# --- resend ---


def test_v3_commit_email_resend_requires_login(tp):
    claimant = baker.make("users.User")
    commit_author_email = _pending_claim(claimant)

    response = tp.post(
        tp.reverse("v3-commit-author-email-resend", pk=commit_author_email.pk)
    )

    tp.response_302(response)
    assert "login" in response.url


def test_v3_commit_email_resend_refuses_other_users_email(user, tp, mailoutbox):
    other_user = baker.make("users.User")
    commit_author_email = _pending_claim(other_user)
    old_hash = commit_author_email.claim_hash

    with tp.login(user):
        response = tp.post(
            tp.reverse("v3-commit-author-email-resend", pk=commit_author_email.pk)
        )

    _assert_refused_with_alert(tp, response)
    commit_author_email.refresh_from_db()
    assert commit_author_email.claimed_by == other_user
    assert commit_author_email.claim_hash == old_hash
    assert not mailoutbox


def test_v3_commit_email_resend_sends_new_verification(user, tp, mailoutbox):
    commit_author_email = _pending_claim(user)
    old_hash = commit_author_email.claim_hash

    with tp.login(user):
        response = tp.post(
            tp.reverse("v3-commit-author-email-resend", pk=commit_author_email.pk)
        )
    tp.response_302(response)

    commit_author_email.refresh_from_db()
    assert commit_author_email.claim_hash != old_hash
    assert len(mailoutbox) == 1


def test_v3_commit_email_resend_refuses_verified_email(user, tp, mailoutbox):
    commit_author_email = _verified_claim(user)

    with tp.login(user):
        response = tp.post(
            tp.reverse("v3-commit-author-email-resend", pk=commit_author_email.pk)
        )
    _assert_refused_with_alert(tp, response)
    assert len(mailoutbox) == 0


def test_v3_commit_email_resend_refuses_email_without_open_ask(user, tp, mailoutbox):
    """Resend must not start a claim for a bound author's other imported
    emails; only an existing open ask can be resent."""
    verified = _verified_claim(user, email="verified@example.com")
    sibling = baker.make(
        "libraries.CommitAuthorEmail",
        email="never-asked@example.com",
        author=verified.author,
        claim_verified=False,
    )

    with tp.login(user):
        response = tp.post(tp.reverse("v3-commit-author-email-resend", pk=sibling.pk))
    _assert_refused_with_alert(tp, response)
    assert len(mailoutbox) == 0


# --- no-JS (non-htmx) error reporting ---
#
# With JS off there is no htmx swap to put a rejection back into the card, and
# the v3 edit template deliberately swallows Django `messages`, so the redirect
# carries the inputs and the profile page regenerates the message from them.
# Each test follows the redirect: the querystring on its own proves nothing the
# user can actually see.


@waffle.testutils.override_flag("v3", active=True)
def test_v3_commit_email_create_no_js_renders_error_and_keeps_value(user, tp):
    with tp.login(user):
        response = tp.post(
            tp.reverse("v3-commit-author-email-create"),
            data={"commit_email": "not-a-real-commit-author@example.com"},
        )
        tp.response_302(response)
        page = tp.get(response.url)

    tp.response_200(page)
    content = page.content.decode()
    assert "field--error" in content
    assert "Email address is not associated with any commits." in content
    # the rejected address is handed back so it does not have to be retyped
    assert 'value="not-a-real-commit-author@example.com"' in content


@waffle.testutils.override_flag("v3", active=True)
def test_v3_commit_email_create_no_js_renders_already_claimed_error(user, tp):
    other_user = baker.make("users.User")
    commit_author_email = _verified_claim(other_user)

    with tp.login(user):
        response = tp.post(
            tp.reverse("v3-commit-author-email-create"),
            data={"commit_email": commit_author_email.email},
        )
        tp.response_302(response)
        page = tp.get(response.url)

    tp.response_200(page)
    content = page.content.decode()
    assert "field--error" in content
    assert "already been claimed by another user" in content


@waffle.testutils.override_flag("v3", active=True)
def test_v3_commit_email_create_no_js_error_row_replaces_the_noscript_row(user, tp):
    """The card renders exactly one add row. When an error comes back the row
    carrying it is server-rendered outside <noscript>, so the plain fallback
    row must stand down or a JS-off user would see the field twice.
    """
    _verified_claim(user, email="done@example.com")

    with tp.login(user):
        response = tp.post(
            tp.reverse("v3-commit-author-email-create"),
            data={"commit_email": "not-a-real-commit-author@example.com"},
        )
        content = tp.get(response.url).content.decode()

    card = content.split('id="commit-email-card-body"', 1)[1]
    fallback = card.split("<noscript>", 1)[1].split("</noscript>", 1)[0]
    assert "commit-email__add-row" not in fallback
    # and the errored row itself is present, once
    assert card.count('id="field-commit_email"') == 1


@waffle.testutils.override_flag("v3", active=True)
def test_v3_commit_email_add_field_id_does_not_collide_with_account_email(user, tp):
    """_field_text.html derives the input id from the field name, and the edit
    page also renders the account's own `email` field. The card's field is
    named `commit_email` so the two ids stay distinct - sharing one would point
    this card's <label for> and its error's aria-describedby at that other
    input, since it comes first in the document.
    """
    with tp.login(user):
        response = tp.post(
            tp.reverse("v3-commit-author-email-create"),
            data={"commit_email": "not-a-real-commit-author@example.com"},
        )
        content = tp.get(response.url).content.decode()

    assert content.count('id="field-commit_email"') == 1
    assert 'for="field-commit_email"' in content
    assert 'aria-describedby="field-commit_email-error"' in content
    assert 'id="field-commit_email-error"' in content


@waffle.testutils.override_flag("v3", active=True)
def test_v3_commit_email_withdraw_no_js_renders_refusal(user, tp):
    commit_author_email = _verified_claim(user)

    with tp.login(user):
        response = tp.post(
            tp.reverse("v3-commit-author-email-withdraw", pk=commit_author_email.pk)
        )
        _assert_refused_with_alert(tp, response)
        page = tp.get(response.url)

    tp.response_200(page)
    assert "can no longer be changed" in page.content.decode()


@waffle.testutils.override_flag("v3", active=True)
def test_v3_commit_email_resend_no_js_renders_refusal(user, tp, mailoutbox):
    commit_author_email = _verified_claim(user)

    with tp.login(user):
        response = tp.post(
            tp.reverse("v3-commit-author-email-resend", pk=commit_author_email.pk)
        )
        _assert_refused_with_alert(tp, response)
        page = tp.get(response.url)

    tp.response_200(page)
    assert "can no longer be changed" in page.content.decode()
    assert not mailoutbox


@waffle.testutils.override_flag("v3", active=True)
def test_v3_commit_email_no_js_redirect_carries_no_message_text(user, tp):
    """Only the inputs travel in the URL - the address, and a bare flag for a
    refused row action. The message itself is regenerated server-side, so a
    hand-crafted link cannot put arbitrary text in the card.
    """
    verified = _verified_claim(user)

    with tp.login(user):
        rejected_add = tp.post(
            tp.reverse("v3-commit-author-email-create"),
            data={"commit_email": "not-a-real-commit-author@example.com"},
        )
        refused_row = tp.post(
            tp.reverse("v3-commit-author-email-withdraw", pk=verified.pk)
        )

    assert rejected_add.url == (
        "/users/me/?edit=true&ce_email=not-a-real-commit-author%40example.com"
    )
    assert refused_row.url == "/users/me/?edit=true&ce_alert=1"


@waffle.testutils.override_flag("v3", active=True)
def test_v3_commit_email_no_js_falls_back_when_revalidation_passes(user, tp):
    """The add error is regenerated by re-validating the address on the
    redirected GET. If whatever blocked the add cleared in between there is no
    validation error left, so the card must still say something rather than
    render as though nothing had happened.
    """
    claimable = _unclaimed_commit_email()

    with tp.login(user):
        page = tp.get(
            f"{tp.reverse('profile-account')}?edit=true&ce_email={claimable.email}"
        )

    tp.response_200(page)
    content = page.content.decode()
    assert "field--error" in content
    assert "That email address could not be added." in content


def test_v3_commit_email_refusal_is_reported_in_the_card_on_htmx_too(user, tp):
    """The same refusal must surface with JS on: htmx does not swap non-2xx
    responses, so the old 404 was dropped without a trace.
    """
    commit_author_email = _verified_claim(user)

    with tp.login(user):
        response = tp.post(
            tp.reverse("v3-commit-author-email-withdraw", pk=commit_author_email.pk),
            extra={"HTTP_HX_REQUEST": "true"},
        )
    tp.response_200(response)
    assert "can no longer be changed" in response.content.decode()


# --- card rendering ---


def test_v3_commit_email_card_row_actions_by_state(user, tp):
    verified = _verified_claim(user, email="done@example.com")
    pending = _pending_claim(user, email="waiting@example.com")

    with tp.login(user):
        response = tp.post(
            tp.reverse("v3-commit-author-email-resend", pk=pending.pk),
            extra={"HTTP_HX_REQUEST": "true"},
        )
    tp.response_200(response)
    content = response.content.decode()
    assert f"Remove {pending.email}" in content
    assert f"Resend verification email to {pending.email}" in content
    assert f"Remove {verified.email}" not in content
    assert f"Resend verification email to {verified.email}" not in content


def test_v3_commit_email_card_orders_verified_before_pending(user, tp):
    """Rows render grouped by state (verified first, then pending), not
    alphabetically; a-pending would come first under plain email ordering."""
    pending = _pending_claim(user, email="a-pending@example.com")
    verified = _verified_claim(user, email="z-verified@example.com")

    with tp.login(user):
        response = tp.post(
            tp.reverse("v3-commit-author-email-resend", pk=pending.pk),
            extra={"HTTP_HX_REQUEST": "true"},
        )
    tp.response_200(response)
    content = response.content.decode()
    assert content.index(verified.email) < content.index(pending.email)


def test_v3_commit_email_card_hides_unclaimed_sibling_emails(user, tp):
    """A bound author's other imported emails were never claimed by the
    user, so the card must not render them as pending rows."""
    pending = _pending_claim(user, email="asked-for@example.com")
    sibling = baker.make(
        "libraries.CommitAuthorEmail",
        email="never-asked@example.com",
        author=pending.author,
        claim_verified=False,
    )

    with tp.login(user):
        response = tp.post(
            tp.reverse("v3-commit-author-email-resend", pk=pending.pk),
            extra={"HTTP_HX_REQUEST": "true"},
        )
    tp.response_200(response)
    content = response.content.decode()
    assert pending.email in content
    assert sibling.email not in content


# --- verify (the emailed link) ---


@waffle.testutils.override_flag("v3", active=True)
def test_verify_get_for_claimant_shows_confirm_page_and_does_not_verify(user, tp):
    """Opening the link in the claimant's own session must not change
    anything (mail scanners prefetch links); it shows the address and an
    explicit confirm button, in second person."""
    commit_author_email = _pending_claim(user)

    with tp.login(user):
        response = tp.get(
            tp.reverse(
                "commit-author-email-verify", token=str(commit_author_email.claim_hash)
            )
        )
    tp.response_200(response)
    content = response.content.decode()
    assert "You asked to link" in content
    assert "your boost.org account" in content
    assert commit_author_email.email in content
    # the ask page shows the concrete expiry datetime, e.g.
    # "This link expires on July 16, 2026, 2:41 PM UTC."
    expected_expiry = date_format(
        commit_author_email.claim_hash_expiration, "F j, Y, g:i A T"
    )
    assert f"This link expires on {expected_expiry}." in content
    # the csrf token must sit inside the confirmation form itself, not
    # merely somewhere on the page
    form_start = content.find("<form", content.find("mailing-list-confirm__header"))
    assert form_start != -1
    form_end = content.find("</form>", form_start)
    assert form_end != -1
    assert "csrfmiddlewaretoken" in content[form_start:form_end]

    commit_author_email.refresh_from_db()
    assert commit_author_email.claim_verified is False
    assert commit_author_email.author.user is None


@waffle.testutils.override_flag("v3", active=True)
def test_verify_get_outside_claimant_session_shows_generic_failure(user, tp):
    """A valid token viewed logged out or from a different account renders
    the exact same failure page as an unknown token: no confirm button, no
    claim details, so a leaked or forwarded link neither works nor reveals
    anything."""
    commit_author_email = _pending_claim(user)
    other_user = baker.make("users.User")
    other_user.set_password("password")
    other_user.save()

    def _body(response):
        """The confirm component only - the base-template chrome around it
        legitimately differs between logged-in and anonymous sessions."""
        content = response.content.decode()
        start = content.find("mailing-list-confirm__header")
        end = content.find("</main>", start)
        assert start != -1
        assert end != -1
        return content[start:end]

    unknown_response = tp.get(
        tp.reverse("commit-author-email-verify", token=str(uuid.uuid4()))
    )

    anonymous_response = tp.get(
        tp.reverse(
            "commit-author-email-verify", token=str(commit_author_email.claim_hash)
        )
    )
    with tp.login(other_user):
        other_user_response = tp.get(
            tp.reverse(
                "commit-author-email-verify", token=str(commit_author_email.claim_hash)
            )
        )

    for response in (anonymous_response, other_user_response):
        tp.response_200(response)
        content = response.content.decode()
        assert commit_author_email.email not in content
        assert "You asked to link" not in content
        assert _body(response) == _body(unknown_response)


@waffle.testutils.override_flag("v3", active=True)
def test_verify_post_outside_claimant_session_does_not_verify(user, tp):
    """The confirm action never runs on the claimant's behalf: POSTing a
    valid token logged out or as a different user changes nothing and
    renders the generic failure page."""
    commit_author_email = _pending_claim(user)
    other_user = baker.make("users.User")
    other_user.set_password("password")
    other_user.save()

    response = tp.post(
        tp.reverse(
            "commit-author-email-verify", token=str(commit_author_email.claim_hash)
        )
    )
    tp.response_200(response)
    assert "could not be confirmed" in response.content.decode()

    with tp.login(other_user):
        response = tp.post(
            tp.reverse(
                "commit-author-email-verify", token=str(commit_author_email.claim_hash)
            )
        )
    tp.response_200(response)
    assert "could not be confirmed" in response.content.decode()

    commit_author_email.refresh_from_db()
    assert commit_author_email.claim_verified is False
    assert commit_author_email.claimed_by == user
    assert commit_author_email.author.user is None


@waffle.testutils.override_flag("v3", active=True)
def test_verify_email_falls_back_when_claimant_has_no_display_name(
    user, tp, mailoutbox
):
    user.display_name = ""
    user.save()
    commit_author_email = _unclaimed_commit_email()
    with tp.login(user):
        tp.post(
            tp.reverse("v3-commit-author-email-create"),
            data={"commit_email": commit_author_email.email},
        )
    body = mailoutbox[0].body
    assert "A user has asked to link" in body
    assert user.email not in body


@waffle.testutils.override_flag("v3", active=True)
def test_verify_post_by_claimant_verifies_and_binds(user, tp):
    """The confirm button in the claimant's own session completes the claim
    and binds attribution to them, with second-person success copy."""
    user.display_name = "Test Claimant"
    user.save()
    commit_author_email = _pending_claim(user)

    with tp.login(user):
        response = tp.post(
            tp.reverse(
                "commit-author-email-verify", token=str(commit_author_email.claim_hash)
            )
        )
    tp.response_200(response)
    content = response.content.decode()
    assert "successfully confirmed" in content
    assert "associated with your account" in content
    assert "Test Claimant's" not in content

    commit_author_email.refresh_from_db()
    assert commit_author_email.claim_verified is True
    assert commit_author_email.author.user == user


@waffle.testutils.override_flag("v3", active=True)
def test_verify_post_conflicting_verified_sibling_does_not_rebind(user, tp):
    """A verified claim never steals an author on which a different user
    holds another verified claim - and the page must say so instead of
    reporting the commit history as associated."""
    other_user = baker.make("users.User")
    verified = _verified_claim(other_user, email="theirs@example.com")
    pending = baker.make(
        "libraries.CommitAuthorEmail",
        email="contested@example.com",
        author=verified.author,
        claim_verified=False,
        claim_hash=uuid.uuid4(),
        claim_hash_expiration=timezone.now() + timedelta(days=1),
        claimed_by=user,
    )

    with tp.login(user):
        response = tp.post(
            tp.reverse("commit-author-email-verify", token=str(pending.claim_hash))
        )
    tp.response_200(response)
    content = response.content.decode()
    assert "Commit history not linked" in content
    assert "claimed by another user, so it was not linked" in content
    assert "associated with your account" not in content

    pending.refresh_from_db()
    assert pending.claim_verified is True
    pending.author.refresh_from_db()
    assert pending.author.user == other_user


@waffle.testutils.override_flag("v3", active=True)
def test_verify_get_already_verified_shows_friendly_message_to_claimant(user, tp):
    """The 'already verified' state is itself claimant-only; anyone else
    gets the generic failure page so the token reveals nothing."""
    commit_author_email = _pending_claim(user)
    commit_author_email.verify_claim()

    with tp.login(user):
        response = tp.get(
            tp.reverse(
                "commit-author-email-verify", token=str(commit_author_email.claim_hash)
            )
        )
    tp.response_200(response)
    assert "already been verified" in response.content.decode()

    response = tp.get(
        tp.reverse(
            "commit-author-email-verify", token=str(commit_author_email.claim_hash)
        )
    )
    tp.response_200(response)
    assert "already been verified" not in response.content.decode()
    assert "could not be confirmed" in response.content.decode()


@waffle.testutils.override_flag("v3", active=True)
def test_verify_expired_token_shows_failure(user, tp):
    """An expired token fails even in the claimant's own session."""
    commit_author_email = _pending_claim(user)
    commit_author_email.claim_hash_expiration = timezone.now() - timedelta(hours=1)
    commit_author_email.save()

    with tp.login(user):
        response = tp.get(
            tp.reverse(
                "commit-author-email-verify", token=str(commit_author_email.claim_hash)
            )
        )
        tp.response_200(response)
        content = response.content.decode()
        assert "could not be confirmed" in content

        # POSTing the expired token must not verify either
        response = tp.post(
            tp.reverse(
                "commit-author-email-verify", token=str(commit_author_email.claim_hash)
            )
        )
        tp.response_200(response)
    commit_author_email.refresh_from_db()
    assert commit_author_email.claim_verified is False


@waffle.testutils.override_flag("v3", active=True)
def test_verify_unknown_token_and_expired_token_render_the_same_message(user, tp):
    """The failure page is deliberately generic so it does not reveal
    whether a token exists or merely expired, even to the claimant."""
    expired = _pending_claim(user)
    expired.claim_hash_expiration = timezone.now() - timedelta(hours=1)
    expired.save()

    def _body(response):
        content = response.content.decode()
        return content[content.find("mailing-list-confirm__header") :]

    with tp.login(user):
        unknown_response = tp.get(
            tp.reverse("commit-author-email-verify", token=str(uuid.uuid4()))
        )
        expired_response = tp.get(
            tp.reverse("commit-author-email-verify", token=str(expired.claim_hash))
        )
    tp.response_200(unknown_response)
    tp.response_200(expired_response)
    assert "could not be confirmed" in _body(unknown_response)
    assert _body(unknown_response) == _body(expired_response)


@waffle.testutils.override_flag("v3", active=True)
def test_verify_malformed_token_shows_generic_failure(user, tp):
    """The route accepts any string, so a truncated or mangled link must
    render the same generic failure page as an unknown token instead of
    crashing on the UUID lookup - including for logged-in users, whose
    session triggers the claim queries."""
    _pending_claim(user)

    with tp.login(user):
        response = tp.get(tp.reverse("commit-author-email-verify", token="not-a-uuid"))
        tp.response_200(response)
        assert "could not be confirmed" in response.content.decode()

        response = tp.post(tp.reverse("commit-author-email-verify", token="not-a-uuid"))
        tp.response_200(response)
        assert "could not be confirmed" in response.content.decode()


# --- verify with the v3 flag off (legacy flow, preserved untouched) ---


@waffle.testutils.override_flag("v3", active=False)
def test_verify_legacy_get_verifies_immediately(user, tp):
    """With the flag off the pre-v3 behavior is intact: opening the link
    while logged in completes the verification on the spot, binds the author
    to the visitor, and renders the legacy template."""
    commit_author_email = _pending_claim(user)

    with tp.login(user):
        response = tp.get(
            tp.reverse(
                "commit-author-email-verify", token=str(commit_author_email.claim_hash)
            )
        )
    tp.response_200(response)
    content = response.content.decode()
    assert "Commit Author Email Address Confirmation" in content
    assert "successfully confirmed" in content
    assert commit_author_email.email in content

    commit_author_email.refresh_from_db()
    assert commit_author_email.claim_verified is True
    assert commit_author_email.author.user == user


@waffle.testutils.override_flag("v3", active=False)
def test_verify_legacy_invalid_token_shows_reason(user, tp):
    with tp.login(user):
        response = tp.get(
            tp.reverse("commit-author-email-verify", token=str(uuid.uuid4()))
        )
    tp.response_200(response)
    content = response.content.decode()
    assert "could not be confirmed" in content
    assert "No valid commit author found or the token has expired" in content


@waffle.testutils.override_flag("v3", active=False)
def test_verify_legacy_email_content(user, tp, mailoutbox):
    """With the flag off, asking to claim sends the pre-v3 email: the plain
    'Please verify' copy with an HTML alternative, not the v3 template."""
    commit_author_email = _unclaimed_commit_email()

    with tp.login(user):
        tp.post(
            tp.reverse("commit-author-email-create"),
            data={"email": commit_author_email.email},
        )

    assert len(mailoutbox) == 1
    message = mailoutbox[0]
    assert message.subject == "Please verify your email address"
    assert "Please verify your email address by clicking the following link" in (
        message.body
    )
    assert "You asked to link" not in message.body
    html_alternatives = [c for c, t in message.alternatives if t == "text/html"]
    assert html_alternatives and "Verify Email" in html_alternatives[0]


@waffle.testutils.override_flag("v3", active=False)
def test_legacy_create_binds_author_at_ask_time(user, tp):
    """The legacy ask flow is intact: asking to claim immediately binds
    author.user to the asker. claimed_by is recorded too, so the claim
    carries over to the v3 card when the flag flips on."""
    commit_author_email = _unclaimed_commit_email()

    with tp.login(user):
        response = tp.post(
            tp.reverse("commit-author-email-create"),
            data={"email": commit_author_email.email},
        )
    tp.response_200(response)

    commit_author_email.refresh_from_db()
    assert commit_author_email.author.user == user
    assert commit_author_email.claim_hash is not None
    assert commit_author_email.claim_verified is False
    assert commit_author_email.claimed_by == user


@waffle.testutils.override_flag("v3", active=False)
def test_legacy_create_rejects_author_bound_email(user, tp):
    """The legacy form rules are intact: any author.user binding blocks the
    claim, with the pre-v3 message."""
    other_user = baker.make("users.User")
    commit_author_email = _unclaimed_commit_email()
    commit_author_email.author.user = other_user
    commit_author_email.author.save()

    with tp.login(user):
        response = tp.post(
            tp.reverse("commit-author-email-create"),
            data={"email": commit_author_email.email},
        )
    assert response.status_code == 422
    assert "already associated with a user" in response.content.decode()


@waffle.testutils.override_flag("v3", active=False)
def test_legacy_resend_sends_new_verification(user, tp, mailoutbox):
    """The legacy resend is intact: keyed by the author.user binding made at
    ask time, no claimed_by involved."""
    commit_author_email = _unclaimed_commit_email()
    commit_author_email.author.user = user
    commit_author_email.author.save()
    commit_author_email.claim_hash = uuid.uuid4()
    commit_author_email.claim_hash_expiration = timezone.now() + timedelta(days=1)
    commit_author_email.save()
    old_hash = commit_author_email.claim_hash

    with tp.login(user):
        response = tp.post(
            tp.reverse("commit-author-email-verify-resend", claim_hash=str(old_hash))
        )
    tp.response_200(response)

    commit_author_email.refresh_from_db()
    assert commit_author_email.claim_hash != old_hash
    assert len(mailoutbox) == 1
    assert mailoutbox[0].subject == "Please verify your email address"


@waffle.testutils.override_flag("v3", active=False)
def test_verify_legacy_post_not_allowed(user, tp):
    """The legacy view was GET-only; the v3 confirm POST must not exist
    behind the flag."""
    commit_author_email = _pending_claim(user)

    with tp.login(user):
        response = tp.post(
            tp.reverse(
                "commit-author-email-verify", token=str(commit_author_email.claim_hash)
            )
        )
    assert response.status_code == 405
