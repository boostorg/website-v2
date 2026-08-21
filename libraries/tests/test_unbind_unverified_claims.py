"""Tests for the 0045 data migration that undoes ask-time commit attribution.

The migration is exercised through its own function rather than by migrating a
test database: what needs pinning is which bindings it selects, and getting that
wrong in either direction is expensive. Clearing too little leaves one member
holding another's commits and the achievements drawn from them; clearing too
much revokes badges that the next author sync rebinds and re-awards dated today.
"""

from importlib import import_module

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from model_bakery import baker

from libraries.models import CommitAuthor

unbind_unverified_claims = import_module(
    "libraries.migrations.0045_unbind_unverified_commit_author_claims"
).unbind_unverified_claims

pytestmark = pytest.mark.django_db


def _member(email):
    return baker.make(get_user_model(), email=email)


def _author_bound_to(user, emails):
    """One commit author attributed to `user`, owning `emails`.

    `emails` is (address, claimed_by, claim_verified) per row, mirroring how the
    importer and the claim flow between them leave a real author.
    """
    author = baker.make(CommitAuthor, name="sdarwin", user=user)
    for address, claimed_by, verified in emails:
        baker.make(
            "libraries.CommitAuthorEmail",
            author=author,
            email=address,
            claimed_by=claimed_by,
            claim_verified=verified,
        )
    return author


def _run():
    unbind_unverified_claims(apps, None)


def test_an_abandoned_claim_gives_the_commits_back():
    """The case the migration exists for: asked, never confirmed, still bound."""
    member = _member("member@example.com")
    author = _author_bound_to(member, [("someone.else@example.com", member, False)])

    _run()

    author.refresh_from_db()
    assert author.user is None


def test_a_binding_the_matcher_would_remake_is_left_alone():
    """An address matching the account is the automatic rule's own conclusion.

    Clearing it would not stick - the next `update_commit_author_user` sweep
    rebinds it - and each round trip revokes the badges behind it and re-awards
    them dated today. So an abandoned claim on a *different* address does not
    make this binding the migration's business.
    """
    member = _member("member@example.com")
    author = _author_bound_to(
        member,
        [
            ("member@example.com", None, False),
            ("someone.else@example.com", member, False),
        ],
    )

    _run()

    author.refresh_from_db()
    assert author.user == member


def test_a_verified_claim_keeps_its_attribution():
    """Confirming the address is exactly what earns the binding."""
    member = _member("member@example.com")
    author = _author_bound_to(member, [("someone.else@example.com", member, True)])

    _run()

    author.refresh_from_db()
    assert author.user == member


def test_an_author_with_no_claim_of_its_own_is_left_alone():
    """No claim by this member means nothing here says a person asked.

    Deliberately conservative: a binding that no longer matches the account
    email is indistinguishable from one made automatically before the member
    changed that address, so it is not treated as an abandoned claim.
    """
    member = _member("member@example.com")
    author = _author_bound_to(member, [("someone.else@example.com", None, False)])

    _run()

    author.refresh_from_db()
    assert author.user == member


def test_another_members_abandoned_claim_does_not_unbind():
    """A claim only speaks for the member who made it."""
    bound = _member("bound@example.com")
    other = _member("other@example.com")
    author = _author_bound_to(bound, [("someone.else@example.com", other, False)])

    _run()

    author.refresh_from_db()
    assert author.user == bound


def test_a_verified_claim_survives_a_second_abandoned_one():
    """One confirmed address is enough, however many later asks went nowhere.

    This is the only shape in which the verified-claim guard does any work: an
    abandoned claim is present, so the member did start something they never
    finished, but they had already proven a different address on the same author.
    """
    member = _member("member@example.com")
    author = _author_bound_to(
        member,
        [
            ("proven@example.com", member, True),
            ("someone.else@example.com", member, False),
        ],
    )

    _run()

    author.refresh_from_db()
    assert author.user == member
