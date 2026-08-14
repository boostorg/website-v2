import pytest
from django.contrib.auth.models import AnonymousUser
from django.views.generic import TemplateView
from model_bakery import baker

from mailing_list.constants import MAILMAN_LISTS
from mailing_list.mixins import MailingListCardMixin
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
def test_prg_error_param_overrides_account_email(rf, user):
    """The no-JS error PRG echoes back the submitted address, not the account email."""
    context = _context(
        rf, user, "/?ml_state=error&ml_error=Nope&ml_email=typed@example.com"
    )
    assert context["mailing_list_card_state"] == "error"
    assert context["mailing_list_card_user_email"] == "typed@example.com"
