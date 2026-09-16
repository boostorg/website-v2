import pytest
from django.contrib.auth.models import AnonymousUser
from django.views.generic import TemplateView
from model_bakery import baker

from mailing_list.constants import MAILMAN_LISTS
from mailing_list.mixins import MailingListCardMixin
from mailing_list.mixins import is_verified_email_for_user
from mailing_list.models import SubscriptionStatus, UserMailingListSubscription

LIST_ID = MAILMAN_LISTS[0]


class _CardView(MailingListCardMixin, TemplateView):
    template_name = "v3/includes/_mailing_list_card.html"


def _context(rf, user, path="/"):
    request = rf.get(path)
    request.user = user
    view = _CardView()
    view.setup(request)
    return view.get_context_data()


@pytest.fixture
def user(db):
    return baker.make("users.User", email="user@example.com")


@pytest.mark.django_db
def test_card_email_falls_back_to_account_email(rf, user):
    """No subscription: the card pre-fills with the user's registered account email."""
    context = _context(rf, user)
    assert context["mailing_list_card_user_email"] == "user@example.com"


@pytest.mark.django_db
def test_card_email_prefers_subscription_email(rf, user):
    """An existing subscription's email wins over the account email."""
    baker.make(
        UserMailingListSubscription,
        user=user,
        list_id=LIST_ID,
        email="subscriber@example.com",
        status=SubscriptionStatus.ACTIVE,
    )
    context = _context(rf, user)
    assert context["mailing_list_card_user_email"] == "subscriber@example.com"


@pytest.mark.django_db
def test_card_email_empty_for_anonymous(rf):
    """Anonymous users get no pre-filled email."""
    context = _context(rf, AnonymousUser())
    assert context.get("mailing_list_card_user_email") is None


@pytest.mark.django_db
def test_card_context_built_once_per_request(rf, user, django_assert_num_queries):
    """Repeated get_context_data() calls reuse the first result.

    V3Mixin.get_context_data() re-enters self.get_context_data(), so without the
    memo every v3 page paying for this mixin runs its queries twice.
    """
    request = rf.get("/")
    request.user = user
    view = _CardView()
    view.setup(request)

    first = view.get_context_data()
    with django_assert_num_queries(0):
        second = view.get_context_data()

    assert (
        first["mailing_list_card_user_email"] == second["mailing_list_card_user_email"]
    )
    assert (
        first["mailing_list_card_subscribed_ids"]
        == second["mailing_list_card_subscribed_ids"]
    )


@pytest.mark.django_db
def test_card_pending_flags_existing_active_subscription(rf, user):
    """A user with one ACTIVE list and a new PENDING one gets has_active_subscription=True,
    so the card can drop the "verify ownership" phrasing that only makes sense before
    any address has been confirmed.
    """
    baker.make(
        UserMailingListSubscription,
        user=user,
        list_id=MAILMAN_LISTS[0],
        email="user@example.com",
        status=SubscriptionStatus.ACTIVE,
    )
    baker.make(
        UserMailingListSubscription,
        user=user,
        list_id=MAILMAN_LISTS[1],
        email="user@example.com",
        status=SubscriptionStatus.PENDING,
    )
    context = _context(rf, user)
    assert context["mailing_list_card_has_active_subscription"] is True


@pytest.mark.django_db
def test_card_pending_without_active_subscription(rf, user):
    """A user with only a PENDING subscription (no confirmed address yet) gets
    has_active_subscription=False, so "verify ownership" copy still applies.
    """
    baker.make(
        UserMailingListSubscription,
        user=user,
        list_id=LIST_ID,
        email="user@example.com",
        status=SubscriptionStatus.PENDING,
    )
    context = _context(rf, user)
    assert context["mailing_list_card_has_active_subscription"] is False


@pytest.mark.django_db
def test_is_verified_email_matches_account_email(user):
    assert is_verified_email_for_user(user, user.email) is True
    assert is_verified_email_for_user(user, user.email.upper()) is True


@pytest.mark.django_db
def test_is_verified_email_matches_verified_commit_email(user):
    baker.make(
        "libraries.CommitAuthorEmail",
        claimed_by=user,
        claim_verified=True,
        email="commits@example.com",
    )
    assert is_verified_email_for_user(user, "commits@example.com") is True


@pytest.mark.django_db
def test_is_verified_email_rejects_unclaimed_email(user):
    baker.make(
        "libraries.CommitAuthorEmail",
        claimed_by=user,
        claim_verified=False,
        email="pending@example.com",
    )
    assert is_verified_email_for_user(user, "pending@example.com") is False
    assert is_verified_email_for_user(user, "random@example.com") is False


def test_is_verified_email_false_for_anonymous():
    assert is_verified_email_for_user(AnonymousUser(), "user@example.com") is False


@pytest.mark.django_db
def test_prg_error_param_overrides_account_email(rf, user):
    """The no-JS error PRG echoes back the submitted address, not the account email."""
    context = _context(
        rf, user, "/?ml_state=error&ml_error=Nope&ml_email=typed@example.com"
    )
    assert context["mailing_list_card_state"] == "error"
    assert context["mailing_list_card_user_email"] == "typed@example.com"
